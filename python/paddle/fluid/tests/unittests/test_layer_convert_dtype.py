# Copyright (c) 2023 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest

import paddle
import paddle.nn.functional as F
from paddle import fluid, nn
from paddle.fluid import core


class MyModel(paddle.nn.Layer):
    def __init__(self, input_size, hidden_size):
        super().__init__()
        self.linear1 = paddle.nn.Linear(input_size, hidden_size)
        self.linear2 = paddle.nn.Linear(hidden_size, hidden_size)
        self.linear3 = paddle.nn.Linear(hidden_size, 1)
        self.batchnorm = paddle.nn.Sequential(paddle.nn.BatchNorm(hidden_size))
        register_buffer_in_temp = paddle.ones([4, 6])
        self.register_buffer('register_buffer_in', register_buffer_in_temp)

    def forward(self, inputs):
        x = self.linear1(inputs)
        x = F.relu(x)
        x = self.batchnorm(x)
        x = self.linear3(x)
        return x


@unittest.skipIf(
    not core.is_compiled_with_cuda(), "Require compiled with CUDA."
)
class TestDtypeConvert(unittest.TestCase):
    def setUp(self):
        self.batch_size, self.input_size, self.hidden_size = 128, 128, 256

    def verify_trans_dtype(
        self, test_type=None, excluded_layers=None, corrected_dtype=None
    ):
        model = MyModel(self.input_size, self.hidden_size)
        if test_type == 'float16':
            model.float16(excluded_layers=excluded_layers)
        elif test_type == 'bfloat16':
            model.bfloat16(excluded_layers=excluded_layers)
        else:
            model.float(excluded_layers=excluded_layers)

        for name, para in model.named_parameters():
            if 'linear' in name:
                self.assertEqual(para.dtype, corrected_dtype)
            elif 'batchnorm' in name:
                if excluded_layers is None:
                    self.assertEqual(para.dtype, paddle.float32)
                else:
                    self.assertEqual(para.dtype, paddle.float16)

    def test_excluded_layers(self):
        self.verify_trans_dtype(
            test_type='float16',
            excluded_layers=[nn.Linear],
            corrected_dtype=paddle.float32,
        )
        self.verify_trans_dtype(
            test_type='float16',
            excluded_layers=nn.Linear,
            corrected_dtype=paddle.float32,
        )

    def test_float16(self):
        self.verify_trans_dtype(
            test_type='float16',
            corrected_dtype=paddle.float16,
        )

    def test_bfloat16(self):
        self.verify_trans_dtype(
            test_type='bfloat16',
            corrected_dtype=paddle.bfloat16,
        )

    def test_float32(self):
        paddle.set_default_dtype('float16')
        self.verify_trans_dtype(
            test_type='float32',
            corrected_dtype=paddle.float32,
        )
        paddle.set_default_dtype('float32')

    def test_excluded_layers_type_error(self):
        self.assertRaises(
            AssertionError, self.verify_trans_dtype, excluded_layers=111
        )


@unittest.skipIf(
    not core.is_compiled_with_cuda(), "Require compiled with CUDA."
)
class TestSupportedTypeInfo(unittest.TestCase):
    def test_cpu(self):
        place = fluid.CPUPlace()
        res = paddle.amp.is_float16_supported(place)
        self.assertEqual(res, False)
        res = paddle.amp.is_bfloat16_supported(place)
        self.assertEqual(res, True)

    def test_gpu_fp16_supported(self):
        res = paddle.amp.is_float16_supported()
        self.assertEqual(res, True)
        place = fluid.CUDAPlace(0)
        res = paddle.amp.is_float16_supported(place)
        self.assertEqual(res, True)

    def test_gpu_bf16_unsupported(self):
        res = paddle.amp.is_bfloat16_supported()
        self.assertEqual(res, False)
        place = fluid.CUDAPlace(0)
        res = paddle.amp.is_bfloat16_supported(place)
        self.assertEqual(res, False)


if __name__ == '__main__':
    unittest.main()
