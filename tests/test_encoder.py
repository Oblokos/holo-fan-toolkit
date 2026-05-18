import unittest
from pathlib import Path

from holo_fan.encoder import (
    AUDIO_SIZE,
    BLOCK_SIZE,
    OFFICIAL_HEADER,
    OFFICIAL_LUT,
    VIDEO_SIZE,
    build_bin,
    encode_video_frame,
    pack_line,
)


class EncoderTests(unittest.TestCase):
    def test_official_data_sizes(self):
        self.assertEqual(len(OFFICIAL_HEADER), 812)
        self.assertEqual(OFFICIAL_HEADER[:2], b"\xee\x37")
        self.assertEqual(len(OFFICIAL_LUT), 256)
        self.assertEqual(OFFICIAL_LUT[0], 0)
        self.assertEqual(OFFICIAL_LUT[-1], 255)

    def test_pack_line_uses_high_bits_msb_first(self):
        packed = pack_line([(0x80, 0x40, 0x20)] + [(0, 0, 0)] * 47)

        self.assertEqual(len(packed), 90)
        self.assertEqual(packed[0], 0b10000000)
        self.assertEqual(packed[18], 0b01000000)
        self.assertEqual(packed[36], 0b00100000)
        self.assertEqual(packed[54], 0)
        self.assertEqual(packed[72], 0)

    def test_encode_video_frame_size(self):
        frame = b"\xff\xff\xff" * (96 * 96)
        video = encode_video_frame(frame, 96, 96, 47.5, 47.5)

        self.assertEqual(len(video), VIDEO_SIZE)
        self.assertGreater(sum(value != 0 for value in video), 0)

    def test_build_static_pattern_bin(self):
        class Args:
            output = Path("unused.bin")
            image = None
            video = None
            pattern = "polar-solid-wedges"
            frames = 2
            width = 96
            height = 96
            center_x = 47.5
            center_y = 47.5
            audio = None
            header = "official"
            header_file = None
            padding = "official"
            gamma = None
            min_brightness = None
            change_brightness_lights = 0
            brightness = None
            video_fit = "disc"
            image_fit = "disc"
            rotate = 0
            fit_scale = 1.0
            offset_x = 0
            offset_y = 0

        data = build_bin(Args)
        payload_start = len(OFFICIAL_HEADER)
        payload = data[payload_start : payload_start + 2 * BLOCK_SIZE]

        self.assertEqual(data[:payload_start], OFFICIAL_HEADER)
        self.assertEqual(len(data) % 0x7080, 0)
        self.assertEqual(payload[VIDEO_SIZE:BLOCK_SIZE], b"\x00" * AUDIO_SIZE)


if __name__ == "__main__":
    unittest.main()
