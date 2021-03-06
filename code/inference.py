import os
from args import parse_args
from dkt.dataloader import Preprocess
from dkt import trainer
import torch


def main(args):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.device = device

    preprocess = Preprocess(args)

    print("loading test data...")
    preprocess.load_test_data(args.test_file_name)

    print("get preprocessed data...")
    test_data = preprocess.get_test_data()

    trainer.inference(args, test_data)


if __name__ == "__main__":
    args = parse_args(mode="train")
    args.model_dir = f"{args.model_dir}/{args.wandb_run_name}"

    main(args)
