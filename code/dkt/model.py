import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import copy
import math

try:
    from transformers.modeling_bert import BertConfig, BertEncoder, BertModel
except:
    from transformers.models.bert.modeling_bert import (
        BertConfig,
        BertEncoder,
        BertModel,
    )


class LSTM(nn.Module):

    def __init__(self, args):
        super(LSTM, self).__init__()
        self.args = args
        self.device = args.device

        self.hidden_dim = self.args.hidden_dim
        self.n_layers = self.args.n_layers

        # categorical features 
        self.categorical_layers = nn.ModuleList([nn.Embedding(x, self.hidden_dim//3) for x in self.args.cate_embs])
        self.categorical_comb = nn.Linear((self.hidden_dim//3)*args.n_cates, self.hidden_dim//3)

        # continuous features
        self.continuous_layers = nn.Linear(args.n_cons, self.hidden_dim//3)

        # categorical and continuous combination projection
        self.comb_proj = nn.Linear(self.hidden_dim//3*2, self.hidden_dim)

        self.lstm = nn.LSTM(self.hidden_dim,
                            self.hidden_dim,
                            self.n_layers,
                            batch_first=True)
        
        # Fully connected layer
        self.fc = nn.Linear(self.hidden_dim, 1)

        self.activation = nn.Sigmoid()

    def init_hidden(self, batch_size):
        h = torch.zeros(
            self.n_layers,
            batch_size,
            self.hidden_dim)
        h = h.to(self.device)

        c = torch.zeros(
            self.n_layers,
            batch_size,
            self.hidden_dim)
        c = c.to(self.device)

        return (h, c)

    def forward(self, input):

        categorical, continuous, _, _ = input
        batch_size = categorical[0].size(0)

        # categorical
        categorical = [cates_layer(categorical[i]) for i, cates_layer in enumerate(self.categorical_layers)]
        categorical = torch.cat(categorical, -1)
        x_cates = self.categorical_comb(categorical)
        
        # continuous
        continuous = torch.cat([c.unsqueeze(-1) for c in continuous], -1).to(torch.float32).to(args.device)
        x_cons = self.continuous_layers(continuous)

        embed = torch.cat([x_cates, x_cons], -1)
        X = self.comb_proj(embed)

        hidden = self.init_hidden(batch_size)
        out, hidden = self.lstm(X, hidden)
        out = out.contiguous().view(batch_size, -1, self.hidden_dim)

        out = self.fc(out)
        preds = self.activation(out).view(batch_size, -1)

        return preds


class LSTMATTN(nn.Module):

    def __init__(self, args):
        super(LSTMATTN, self).__init__()
        self.args = args
        self.device = args.device

        self.hidden_dim = self.args.hidden_dim
        self.n_layers = self.args.n_layers
        self.n_heads = self.args.n_heads
        self.drop_out = self.args.drop_out

        ## categorical features 
        self.categorical_layers = nn.ModuleList([nn.Embedding(x, self.hidden_dim//3) for x in self.args.cate_embs])
        self.categorical_comb = nn.Linear((self.hidden_dim//3)*args.n_cates, self.hidden_dim//3)

        # continuous features
        self.continuous_layers = nn.Linear(args.n_cons, self.hidden_dim//3)

        # categorical and continuous combination projection
        self.comb_proj = nn.Linear(self.hidden_dim//3*2, self.hidden_dim)

        self.lstm = nn.LSTM(self.hidden_dim,
                            self.hidden_dim,
                            self.n_layers,
                            batch_first=True)
        
        self.config = BertConfig( 
            3, # not used
            hidden_size=self.hidden_dim,
            num_hidden_layers=1,
            num_attention_heads=self.n_heads,
            intermediate_size=self.hidden_dim,
            hidden_dropout_prob=self.drop_out,
            attention_probs_dropout_prob=self.drop_out,
        )
        self.attn = BertEncoder(self.config)            
    
        # Fully connected layer
        self.fc = nn.Linear(self.hidden_dim, 1)

        self.activation = nn.Sigmoid()

    def init_hidden(self, batch_size):
        h = torch.zeros(
            self.n_layers,
            batch_size,
            self.hidden_dim)
        h = h.to(self.device)

        c = torch.zeros(
            self.n_layers,
            batch_size,
            self.hidden_dim)
        c = c.to(self.device)

        return (h, c)

    def forward(self, input):

        categorical, continuous, _, _ = input
        batch_size = categorical[0].size(0)

        # categorical
        categorical = [cates_layer(categorical[i]) for i, cates_layer in enumerate(self.categorical_layers)]
        categorical = torch.cat(categorical, -1)
        x_cates = self.categorical_comb(categorical)
        
        # continuous
        continuous = torch.cat([c.unsqueeze(-1) for c in continuous], -1).to(torch.float32).to(args.device)
        x_cons = self.continuous_layers(continuous)

        embed = torch.cat([x_cates, x_cons], -1)
        X = self.comb_proj(embed)

        hidden = self.init_hidden(batch_size)
        out, hidden = self.lstm(X, hidden)
        out = out.contiguous().view(batch_size, -1, self.hidden_dim)
                
        extended_attention_mask = mask.unsqueeze(1).unsqueeze(2)
        extended_attention_mask = extended_attention_mask.to(dtype=torch.float32)
        extended_attention_mask = (1.0 - extended_attention_mask) * -10000.0
        head_mask = [None] * self.n_layers
        
        encoded_layers = self.attn(out, extended_attention_mask, head_mask=head_mask)        
        sequence_output = encoded_layers[-1]
        
        out = self.fc(sequence_output)

        preds = self.activation(out).view(batch_size, -1)

        return preds


class Bert(nn.Module):

    def __init__(self, args):
        super(Bert, self).__init__()
        self.args = args
        self.device = args.device

        # Defining some parameters
        self.hidden_dim = self.args.hidden_dim
        self.n_layers = self.args.n_layers

        # categorical features 
        self.categorical_layers = nn.ModuleList([nn.Embedding(x, self.hidden_dim//3) for x in self.args.cate_embs])
        self.categorical_comb = nn.Linear((self.hidden_dim//3)*args.n_cates, self.hidden_dim//3)

        # continuous features
        self.continuous_layers = nn.Linear(args.n_cons, self.hidden_dim//3)

        # categorical and continuous combination projection
        self.comb_proj = nn.Linear(self.hidden_dim//3*2, self.hidden_dim)

        # Bert config
        self.config = BertConfig( 
            3, # not used
            hidden_size=self.hidden_dim,
            num_hidden_layers=self.args.n_layers,
            num_attention_heads=self.args.n_heads,
            max_position_embeddings=self.args.max_seq_len          
        )

        # Defining the layers
        # Bert Layer
        self.encoder = BertModel(self.config)  

        # Fully connected layer
        self.fc = nn.Linear(self.args.hidden_dim, 1)
       
        self.activation = nn.Sigmoid()


    def forward(self, input):
        categorical, continuous, _, _ = input
        batch_size = categorical[0].size(0)

        # categorical
        categorical = [cates_layer(categorical[i]) for i, cates_layer in enumerate(self.categorical_layers)]
        categorical = torch.cat(categorical, -1)
        x_cates = self.categorical_comb(categorical)
        
        # continuous
        continuous = torch.cat([c.unsqueeze(-1) for c in continuous], -1).to(torch.float32).to(args.device)
        x_cons = self.continuous_layers(continuous)

        embed = torch.cat([x_cates, x_cons], -1)
        X = self.comb_proj(embed)

        # Bert
        encoded_layers = self.encoder(inputs_embeds=X, attention_mask=mask)
        out = encoded_layers[0]
        out = out.contiguous().view(batch_size, -1, self.hidden_dim)
        out = self.fc(out)
        preds = self.activation(out).view(batch_size, -1)

        return preds