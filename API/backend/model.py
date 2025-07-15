import torch
import torch.nn as nn
import torch.nn.functional as F

# ==================================================
# Core Blocks
# ==================================================
class DoubleConv(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.double_conv = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True)
        )
    def forward(self, x):
        return self.double_conv(x)

class AttentionGate(nn.Module):
    def __init__(self, F_g, F_l, F_int):
        super().__init__()
        self.W_g = nn.Sequential(
            nn.Conv2d(F_g, F_int, 1, bias=False),
            nn.BatchNorm2d(F_int)
        )
        self.W_x = nn.Sequential(
            nn.Conv2d(F_l, F_int, 1, bias=False),
            nn.BatchNorm2d(F_int)
        )
        self.psi = nn.Sequential(
            nn.Conv2d(F_int, 1, 1, bias=False),
            nn.BatchNorm2d(1),
            nn.Sigmoid()
        )
        self.relu = nn.ReLU(inplace=True)
    def forward(self, g, x):
        psi = self.relu(self.W_g(g) + self.W_x(x))
        psi = self.psi(psi)
        return x * psi

class ASPP(nn.Module):
    def __init__(self, in_channels, out_channels, rates=(1,6,12,18)):
        super().__init__()
        self.branches = nn.ModuleList([
            nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 3, padding=r, dilation=r, bias=False),
                nn.BatchNorm2d(out_channels), nn.ReLU(inplace=True)
            ) for r in rates
        ])
        self.branches.append(
            nn.Sequential(
                nn.AdaptiveAvgPool2d(1),
                nn.Conv2d(in_channels, out_channels, 1, bias=False),
                nn.BatchNorm2d(out_channels), nn.ReLU(inplace=True)
            )
        )
        self.project = nn.Sequential(
            nn.Conv2d(len(self.branches)*out_channels, out_channels, 1, bias=False),
            nn.BatchNorm2d(out_channels), nn.ReLU(inplace=True),
            nn.Dropout(0.5)
        )
    def forward(self, x):
        size = x.shape[-2:]
        feats = [b(x) for b in self.branches[:-1]]
        pooled = self.branches[-1](x)
        pooled = F.interpolate(pooled, size, mode='bilinear', align_corners=False)
        feats.append(pooled)
        x = torch.cat(feats, dim=1)
        return self.project(x)

# ==================================================
# Final Model: AttentionUNet2p5D_ASPP
# ==================================================
class AttentionUNet2p5D_ASPP(nn.Module):
    def __init__(self, in_channels=5, out_channels=1):
        super().__init__()
        feats = [64, 128, 256, 512]
        self.conv1, self.pool1 = DoubleConv(in_channels, feats[0]), nn.MaxPool2d(2)
        self.conv2, self.pool2 = DoubleConv(feats[0], feats[1]), nn.MaxPool2d(2)
        self.conv3, self.pool3 = DoubleConv(feats[1], feats[2]), nn.MaxPool2d(2)
        self.conv4, self.pool4 = DoubleConv(feats[2], feats[3]), nn.MaxPool2d(2)

        self.bottleneck = DoubleConv(feats[3], feats[3]*2)
        self.aspp       = ASPP(feats[3]*2, feats[3]*2)

        self.up4, self.att4 = nn.ConvTranspose2d(feats[3]*2, feats[3], 2, 2), AttentionGate(feats[3], feats[3], feats[3]//2)
        self.dec4 = DoubleConv(feats[3]*2, feats[3])
        self.up3, self.att3 = nn.ConvTranspose2d(feats[3], feats[2], 2, 2), AttentionGate(feats[2], feats[2], feats[2]//2)
        self.dec3 = DoubleConv(feats[2]*2, feats[2])
        self.up2, self.att2 = nn.ConvTranspose2d(feats[2], feats[1], 2, 2), AttentionGate(feats[1], feats[1], feats[1]//2)
        self.dec2 = DoubleConv(feats[1]*2, feats[1])
        self.up1, self.att1 = nn.ConvTranspose2d(feats[1], feats[0], 2, 2), AttentionGate(feats[0], feats[0], feats[0]//2)
        self.dec1 = DoubleConv(feats[0]*2, feats[0])
        self.conv_final = nn.Conv2d(feats[0], out_channels, 1)

    def forward(self, x):
        c1 = self.conv1(x);  p1 = self.pool1(c1)
        c2 = self.conv2(p1); p2 = self.pool2(c2)
        c3 = self.conv3(p2); p3 = self.pool3(c3)
        c4 = self.conv4(p3); p4 = self.pool4(c4)

        bn = self.bottleneck(p4); bn = self.aspp(bn)

        d4 = self.up4(bn); c4a = self.att4(d4, c4); d4 = self.dec4(torch.cat([c4a, d4], dim=1))
        d3 = self.up3(d4); c3a = self.att3(d3, c3); d3 = self.dec3(torch.cat([c3a, d3], dim=1))
        d2 = self.up2(d3); c2a = self.att2(d2, c2); d2 = self.dec2(torch.cat([c2a, d2], dim=1))
        d1 = self.up1(d2); c1a = self.att1(d1, c1); d1 = self.dec1(torch.cat([c1a, d1], dim=1))
        return self.conv_final(d1)
