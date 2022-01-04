from torch import nn
import torch
from BasicModules import Encoder
from data_related.utils import Config

"""
# Configuration
  - ELECTRA-SMALL : 
  {
      "number-of-layers" : 12,
      "hidden-size" : 256,
      "sequence-length" : 128,
      "ffn-inner-hidden-size" : 1024,
      "attention-heads" : 4,
      "warmup-steps" : 10000,
      "learning-rate" : 5e-4,
      "batch-size" : 128,
      "train-steps" : 1450000,
      "save-steps" : 100000
  }
"""


class BERT(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config

        self.encoder = Encoder(self.config)

        self.linear = nn.Linear(config.d_hidn, config.d_hidn)
        self.activation = torch.tanh
        # (bs, n_enc_seq, d_hidn)

    def forward(self, inputs):
        # (bs, n_seq, d_hidn), [(bs, n_head, n_enc_seq, n_enc_seq)]
        outputs, self_attn_probs = self.encoder(inputs)
        # (bs, d_hidn)
        outputs_cls = outputs[:, 0].contiguous()
        outputs_cls = self.linear(outputs_cls)
        outputs_cls = self.activation(outputs_cls)
        # (bs, n_enc_seq, n_enc_vocab), (bs, d_hidn), [(bs, n_head, n_enc_seq, n_enc_seq)]
        return outputs, outputs_cls, self_attn_probs

    def save(self, epoch, loss, path):
        torch.save({
            "epoch": epoch,
            "loss": loss,
            "state_dict": self.state_dict()
        }, path)

    def load(self, path):
        save = torch.load(path)
        self.load_state_dict(save["state_dict"])
        return save["epoch"], save["loss"]


class ELECTRA_DISCRIMINATOR(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.bert = BERT(config)
        self.discriminator = nn.Linear(config.d_hidn, 2, bias=False)
        self.sigmoid = nn.Sigmoid()

    def forward(self, inputs):
        # (bs, n_enc_seq, d_hidn), (bs, d_hidn), [(bs, n_head, n_enc_seq, n_enc_seq)]
        outputs, outputs_cls, attn_probs = self.bert(inputs)
        # (bs, 2)
        cls_logit = self.discriminator(outputs)
        cls_logit = self.sigmoid(cls_logit)
        return cls_logit, attn_probs


class ELECTRA_GENERATOR(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.bert = BERT(config)
        self.language_model = nn.Linear(config.d_hidn, config.n_enc_vocab, bias=True)
        """
        Example.)
        입력 Sentence
        - She is a lovely person who has powerful energy and delightful
        Step.1) Tokenization : 5  [MASK] 7 8 9 10 11 12 13 [MASK] 15
          - Mask Ratio 는 전체 길이의 15 % uniform 이라 하는데, 다른 분포가 좋을 것 같긴 함
          - 어쨌든 실험은 공평하게 해야하기에 Uniform distribution 에서 뽑아오기 
        Step.2) Replacement : 5  22 7 8 9 10 11 12 13 34 15 
          - 이 때, Generator 로부터 샘플링
        Generator 는 masked 된 곳의 token 을 Prediction (log from)
        """
    def forward(self, inputs):
        outputs, outputs_cls, attn_probs = self.bert(inputs)
        lm_outs = self.language_model(outputs)
        # (BS, n_enc_seq, n_enc_vocab)
        return lm_outs


def weight_sync(src_model, tgt_model):
    tgt_model.encoder.enc_emb.weight = src_model.encoder.enc_emb.weight
    tgt_model.encoder.pos_emb.weight = src_model.encoder.pos_emb.weight


# cfg = Config({"n_enc_vocab": 30522,
#               "n_enc_seq": 128,
#               "n_seg_type": 2,
#               "n_layer": 12,
#               "d_hidn": 256,
#               "i_pad": 0,
#               "d_ff": 512,
#               "n_head": 4,
#               "d_head": 64,
#               "dropout": 0.1,
#               "layer_norm_epsilon": 1e-12
#               })
#
# EG = ELECTRA_GENERATOR(cfg)
#
# param_cnt = []
# import numpy as np
#
# for param in EG.parameters():
#     if param.requires_grad:
#         param_cnt += list(param.view(-1).shape)
#
# print(np.sum(param_cnt)/1e7)