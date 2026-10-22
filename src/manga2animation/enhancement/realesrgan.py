"""Chạy checkpoint Real-ESRGAN animevideov3 bằng PyTorch, không cần NCNN.

Kiến trúc tương ứng SRVGGNetCompact của Xintao Wang, BSD-3-Clause.
Nguồn: https://github.com/xinntao/Real-ESRGAN
Thông tin giấy phép: third_party/Real-ESRGAN-LICENSE.txt.
"""
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.nn import functional as F


class AnimeVideoNet(nn.Module):
    """Mạng SRVGG 16 lớp giữa, khớp tên trọng số của animevideov3 chính thức."""

    def __init__(self):
        super().__init__()
        layers = [nn.Conv2d(3, 64, 3, 1, 1), nn.PReLU(64)]
        for _ in range(16):
            layers.extend([nn.Conv2d(64, 64, 3, 1, 1), nn.PReLU(64)])
        layers.append(nn.Conv2d(64, 48, 3, 1, 1))
        self.body = nn.ModuleList(layers)
        self.upsampler = nn.PixelShuffle(4)

    def forward(self, image):
        features = image
        for layer in self.body:
            features = layer(features)
        return self.upsampler(features) + F.interpolate(image, scale_factor=4, mode='nearest')


class RealESRGANUpscaler:
    """Nạp model một lần, dùng lại cho nhiều panel. Đầu vào/đầu ra đều là ảnh PIL RGB."""

    def __init__(self, model_path, device='cpu', tile=128):
        path = Path(model_path)
        if not path.is_file():
            raise FileNotFoundError(f'Chưa có checkpoint Real-ESRGAN: {path}')
        if tile < 1:
            raise ValueError('Kích thước tile phải lớn hơn 0.')
        self.device = torch.device(f'cuda:{device}' if str(device).isdigit() else device)
        if self.device.type == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('Không dùng được CUDA. Đổi upscale_device thành cpu trong config.')
        self.tile = tile
        self.model = AnimeVideoNet()
        checkpoint = torch.load(path, map_location='cpu', weights_only=True)
        weights = checkpoint.get('params_ema', checkpoint.get('params', checkpoint))
        self.model.load_state_dict(weights, strict=True)
        # Dùng FP32 để tương thích GPU Pascal; không tự chuyển sang half precision.
        self.model.to(self.device).eval()

    @torch.inference_mode()
    def upscale(self, image, scale=2):
        """Phóng lớn ảnh; model chạy ×4 rồi thu về tỷ lệ đầu ra mong muốn."""
        if not 1 <= scale <= 4:
            raise ValueError('Tỷ lệ upscale phải nằm trong [1, 4].')
        rgb = image.convert('RGB')
        source = np.asarray(rgb, dtype=np.float32) / 255
        width, height = rgb.size
        output = np.empty((height * 4, width * 4, 3), dtype=np.uint8)
        # Mạng có 18 lớp convolution 3×3: lấy thêm 18 pixel quanh tile để tránh đường nối.
        padding = 18
        for y in range(0, height, self.tile):
            for x in range(0, width, self.tile):
                right, bottom = min(x + self.tile, width), min(y + self.tile, height)
                left_pad, top_pad = max(0, x-padding), max(0, y-padding)
                right_pad, bottom_pad = min(width, right+padding), min(height, bottom+padding)
                patch = source[top_pad:bottom_pad, left_pad:right_pad]
                tensor = torch.from_numpy(patch.copy()).permute(2, 0, 1).unsqueeze(0).to(self.device)
                prediction = self.model(tensor)[0]
                # Chỉ giữ phần giữa; vùng biên mở rộng chỉ cung cấp ngữ cảnh cho model.
                prediction = prediction[:, (y-top_pad)*4:(bottom-top_pad)*4,
                                        (x-left_pad)*4:(right-left_pad)*4]
                pixels = prediction.clamp(0, 1).permute(1, 2, 0).cpu().numpy()
                output[y*4:bottom*4, x*4:right*4] = np.rint(pixels*255).astype(np.uint8)
        result = Image.fromarray(output)
        if scale != 4:
            result = result.resize((round(width*scale), round(height*scale)), Image.Resampling.LANCZOS)
        return result
