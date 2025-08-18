import torch
import torch.nn as nn
import torch.nn.functional as F
import librosa
import numpy as np
from torchaudio.models import Conformer
from intervaltree import Interval, IntervalTree
from config_utils import load_config

cfg = load_config("config.yaml")

# ===== Feature Extractor =====
def zcr_extractor(wav, win_length, hop_length):
    pad_length = win_length // 2
    wav = np.pad(wav, (pad_length, pad_length), 'constant')
    num_frames = 1 + (wav.shape[0] - win_length) // hop_length
    zcrs = np.zeros(num_frames)
    for i in range(num_frames):
        start = i * hop_length
        end = start + win_length
        zcr = np.abs(np.sign(wav[start+1:end]) - np.sign(wav[start:end-1]))
        zcr = np.sum(zcr) * 0.5 / win_length
        zcrs[i] = zcr
    return zcrs.astype(np.float32)

def feature_extractor(wav, sr=cfg["audio"]["sample_rate"]):
    mel = librosa.feature.melspectrogram(
        y=wav,
        sr=sr,
        n_fft=cfg["audio"]["n_fft"],
        hop_length=cfg["audio"]["hop_length"],
        n_mels=cfg["audio"]["n_mels"]
    )
    mel = librosa.power_to_db(mel, ref=np.max)

    zcr = zcr_extractor(wav,
        win_length=cfg["audio"]["win_length"],
        hop_length=cfg["audio"]["hop_length"]
    )
    vms = np.var(mel, axis=0)

    mel = torch.tensor(mel).unsqueeze(0)
    zcr = torch.tensor(zcr).unsqueeze(0)
    vms = torch.tensor(vms).unsqueeze(0)

    zcr = zcr.unsqueeze(1).expand(-1, cfg["audio"]["n_mels"], -1)
    vms = torch.var(mel, dim=1).unsqueeze(1).expand(-1, mel.shape[1], -1)

    feature = torch.stack((mel, vms, zcr), dim=1)
    length = torch.tensor([zcr.shape[-1]])
    return feature, length

# ===== Models use cfg =====
class Conv2dDownsampling(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Sequential(
            nn.Conv2d(cfg["model"]["conv2d"]["in_channels"],
                      cfg["model"]["conv2d"]["out_channels"],
                      kernel_size=3, stride=2),
            nn.ReLU(),
        )
        self.conv2 = nn.Sequential(
            nn.Conv2d(cfg["model"]["conv2d"]["out_channels"],
                      cfg["model"]["conv2d"]["out_channels"],
                      kernel_size=3, stride=2),
            nn.ReLU(),
        )
    def forward(self, x, length):
        keep_dim_padding = 1 - x.shape[-1] % 2
        x = F.pad(x, (0, keep_dim_padding, 0, 0))
        x = self.conv1(x)
        length = (length - 3 + keep_dim_padding) // 2 + 1

        keep_dim_padding = 1 - x.shape[-1] % 2
        x = F.pad(x, (0, keep_dim_padding, 0, 0))
        x = self.conv2(x)
        length = (length - 3 + keep_dim_padding) // 2 + 1
        return x, length


class Conv1dUpsampling(nn.Module):
    def __init__(self):
        super().__init__()
        self.deconv = nn.Sequential(
            nn.ConvTranspose1d(cfg["model"]["conv1d"]["in_channels"],
                               cfg["model"]["conv1d"]["out_channels"],
                               kernel_size=3, stride=2),
            nn.ReLU(),
            nn.ConvTranspose1d(cfg["model"]["conv1d"]["out_channels"],
                               cfg["model"]["conv1d"]["out_channels"],
                               kernel_size=3, stride=2),
            nn.ReLU(),
        )
    def forward(self, x):
        return self.deconv(x)


class DetectionNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.downsampling = Conv2dDownsampling()
        self.upsampling = Conv1dUpsampling()
        self.linear = nn.Linear(cfg["model"]["linear_input"], cfg["model"]["linear_output"])
        self.dropout = nn.Dropout(cfg["model"]["dropout"])
        self.conformer = Conformer(**cfg["model"]["conformer"])
        self.lstm = nn.LSTM(**cfg["model"]["lstm"])
        lstm_hidden = cfg["model"]["lstm"]["hidden_size"]
        fc_input_dim = lstm_hidden * 2
        self.fc = nn.Linear(fc_input_dim, cfg["model"]["fc_output"])
        self.sigmoid = nn.Sigmoid()

    def forward(self, x, length):
        sequence = x.shape[-1]
        x, length = self.downsampling(x, length)
        x = x.squeeze(1).transpose(1, 2).contiguous()
        x = self.linear(x)
        x = self.dropout(x)
        x = self.conformer(x, length)[0]
        x = x.transpose(1, 2).contiguous()
        x = self.upsampling(x)
        x = x.transpose(1, 2).contiguous()
        x = self.lstm(x)[0]
        x = self.fc(x)
        x = self.sigmoid(x.squeeze(-1))
        return x[:, :sequence]


class BreathDetector:
    def __init__(self, model, device=None):
        self.model = model
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def __call__(self, wav_path):
        wav, sr = librosa.load(wav_path, sr=cfg["audio"]["sample_rate"])
        feature, length = feature_extractor(wav, sr)
        feature, length = feature.to(self.device), length.to(self.device)
        output = self.model(feature, length)

        prediction = (output[0] > cfg["detection"]["threshold"]).nonzero().squeeze().tolist()
        tree = IntervalTree()
        if isinstance(prediction, list) and len(prediction) > 1:
            diffs = np.diff(prediction)
            splits = np.where(diffs != 1)[0] + 1
            splits = np.split(prediction, splits)
            splits = list(filter(lambda split: len(split) > cfg["detection"]["min_length"], splits))
            for split in splits:
                if split[-1] * cfg["detection"]["frame_shift"] > split[0] * cfg["detection"]["frame_shift"]:
                    tree.add(Interval(
                        round(split[0] * cfg["detection"]["frame_shift"], 2),
                        round(split[-1] * cfg["detection"]["frame_shift"], 2)
                    ))
        return tree

