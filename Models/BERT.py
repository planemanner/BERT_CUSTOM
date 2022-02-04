from torch import nn
import torch
from .BasicModules import Encoder
from data_related.utils import Config
import yaml


class BERT(nn.Module):
    def __init__(self, config):
        super(BERT, self).__init__()

        self.encoder = Encoder(config)

        # (bs, n_enc_seq, d_hidn)

    def forward(self, inputs):
        # (bs, n_seq, d_hidn), [(bs, n_head, n_enc_seq, n_enc_seq)]
        outputs, self_attn_probs = self.encoder(inputs)
        # (bs, d_hidn)

        # (bs, n_enc_seq, n_enc_vocab), (bs, d_hidn), [(bs, n_head, n_enc_seq, n_enc_seq)]
        return outputs, self_attn_probs


class ELECTRA_DISCRIMINATOR(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.bert = BERT(config)
        self.projector = nn.Linear(config.d_head * config.n_head, config.d_hidn)
        self.activation = nn.GELU()
        self.discriminator = nn.Linear(config.d_hidn, 1, bias=False)
        self.final_act = nn.Sigmoid()

    def forward(self, inputs):
        # (bs, n_enc_seq, d_hidn), (bs, d_hidn), [(bs, n_head, n_enc_seq, n_enc_seq)]
        outputs, attn_probs = self.bert(inputs)
        # (bs, 2)
        outputs = self.projector(outputs)
        outputs = self.activation(outputs)
        cls_logit = self.discriminator(outputs)

        return self.final_act(cls_logit)


class ELECTRA_GENERATOR(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.bert = BERT(config)
        self.activation = torch.nn.GELU()
        self.layer_norm = nn.LayerNorm(config.d_head * config.n_head, eps=config.layer_norm_epsilon)
        self.language_model = nn.Linear(config.d_head * config.n_head, config.n_enc_vocab, bias=True)
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
        outputs, attn_probs = self.bert(inputs)
        '''BERT output Shape : (BS, num_seq, d_head * n_head)'''
        outputs = self.activation(outputs)
        outputs = self.layer_norm(outputs)
        lm_outs = self.language_model(outputs)
        # (BS, n_enc_seq, n_enc_vocab)
        return lm_outs


def weight_sync(src_model, tgt_model):
    tgt_model.encoder.enc_emb.weight.data.copy_(src_model.encoder.enc_emb.weight.data)
    tgt_model.encoder.pos_emb.weight.data.copy_(src_model.encoder.pos_emb.weight.data)


