"""
Pytorch utils.

The latest version of Pytorch (in the main branch 2018.06.30)
supports tensor flipping.
"""
import numpy as np
import re
import torch
from torch import tensor
import torch.nn.functional as F
from torch import tensor
from heapq import heappush, heappop
from cnns.nnlib.utils.general_utils import plot_signal_freq
from cnns.nnlib.utils.general_utils import mem_log_file
import gc
from functools import reduce
from cnns.nnlib.utils.log_utils import get_logger
from cnns.nnlib.utils.log_utils import set_up_logging
import logging

logger = get_logger(name=__name__)
logger.setLevel(logging.DEBUG)
logger.info("Set up test")


class MockContext(object):
    """
    Mock context class for 1D and 2D convolution. We use it to pass intermediate
    results from the forward to backward pass.
    """

    def __init__(self):
        """
        Set everything to None at the very beginning.
        """
        super(MockContext, self).__init__()
        self.args = None
        self.needs_input_grad = None

    def save_for_backward(self, *args):
        """
        Save intermediate results in the forward pass for the backward pass.
        :param args: the intermediate results to be saved.
        """
        self.args = args

    @property
    def saved_tensors(self):
        """
        Retrieve the saved tensors in the forward pass for the backward pass.
        :return: the saved tensors
        """
        return self.args

    def set_needs_input_grad(self, number_needed):
        """
        Set the need for gradients (for the backward pass).

        :param number_needed: how many gradients do we need: for example for the
        input map and the filters.
        """
        self.needs_input_grad = [True for _ in range(number_needed)]


def get_fft_sizes(input_size, filter_size, output_size, padding_count):
    """
    We have to pad input with (filter_size - 1) to execute fft correctly
    (no overlapping signals) and optimize it by extending the signal to the next
    power of 2.
    We want to reuse the fft-ed input x, so we use the larger size chosen from:
    the filter size or output size. Larger padding does not hurt correctness of
    fft but make it slightly slower, in terms of the computation time.

    >>> fft_size, half_fft_size = get_fft_sizes(10, 3, None, 1)
    >>> # print("fft_size: ", fft_size)
    >>> assert fft_size == 32
    >>> assert half_fft_size == 17

    >>> fft_size, half_fft_size = get_fft_sizes(10, 3, 6, 0)
    >>> # print("fft_size: ", fft_size)
    >>> assert fft_size == 16
    >>> assert half_fft_size == 9

    >>> fft_size, half_fft_size = get_fft_sizes(10, 3, 7, 3)
    >>> # print("fft_size: ", fft_size)
    >>> assert fft_size == 32
    >>> assert half_fft_size == 17

    :param input_size: the size of the input for one of the dimensions
    :param filter_size: the size of the filter for one of the dimensions
    :param output_size: the size of the output for one of the dimensions
    :param padding_count: the padding applied to the input for the chosen
    dimension
    :return: the size of the ffted signal (and its onesided size) for the chosen
    dimension
    """
    if output_size is None:
        output_size = input_size - filter_size + 1 + 2 * padding_count
    size = max(filter_size, output_size)
    init_fft_size = next_power2(input_size + size - 1 + 2 * padding_count)
    init_half_fft_size = init_fft_size // 2 + 1
    return init_fft_size, init_half_fft_size


def get_pair(value=None, val_1_default=None, val2_default=None, name="value"):
    """
    >>> v1, v2 = get_pair(9)
    >>> assert v1 == 9
    >>> assert v2 == 9

    >>> value = (8, 1)
    >>> v1, v2 = get_pair(value=value)
    >>> assert v1 == 8
    >>> assert v2 == 1

    >>> v1, v2 = get_pair(val_1_default=3, val2_default=4)
    >>> assert v1 == 3
    >>> assert v2 == 4

    >>> v1, v2 = get_pair((1, 2, 3))
    Traceback (most recent call last):
    ...
    ValueError: value requires a tuple of length 2

    Extend a single value to a 2-element tuple with the same values or just
    return the tuple: value.

    :param value: a number or a tuple
    :param val_1_default: default fist value
    :param val2_default: default second value
    :param name: the name of the value
    :return: the 2-element tuple
    """
    if value is None:
        return val_1_default, val2_default
    if isinstance(value, type(0.0)) or isinstance(value, type(0)):
        return value, value
    elif isinstance(value, type(())) or isinstance(value, type([])):
        if len(value) == 2:
            return value
        else:
            raise ValueError(name + " requires a tuple of length 2")


def to_tensor(value):
    """
    `to_tensor` and `from_tensor` methods are used to transfer intermediate
    results between forward and backward pass of the convolution.

    Transform from None to -1 or retain the initial value
    for transition from a value or None to a tensor.

    :param value: a value to be changed to a tensor
    :return: a tensor representing the value, tensor with value -1 represents
    the None input
    """
    if value is None:
        return tensor([-1])
    return tensor([value])


def from_tensor(tensor_item):
    """
    `to_tensor` and `from_tensor` methods are used to transfer intermediate
    results between forward and backward pass of the convolution.

    Transform from tensor to a single numerical value or None (a tensor with
    value -1 is transformed to None).

    :param tensor_item: tensor with a single value
    :return: a single numerical value extracted from the tensor or None if the
    value is -1
    """
    value = tensor_item.item()
    if value == -1:
        return None
    return value


def flip(x, dim):
    """
    Flip the tensor x for dimension dim.

    :param x: the input tensor
    :param dim: the dimension according to which we flip the tensor
    :return: flipped tensor
    """
    indices = [slice(None)] * x.dim()
    indices[dim] = torch.arange(x.size(dim) - 1, -1, -1,
                                dtype=torch.long, device=x.device)
    return x[tuple(indices)]


def next_power2(x):
    """
    :param x: an integer number
    :return: the power of 2 which is the larger than x but the
    smallest possible

    >>> result = next_power2(5)
    >>> np.testing.assert_equal(result, 8)
    >>> result = next_power2(1)
    >>> np.testing.assert_equal(result, 1)
    >>> result = next_power2(2)
    >>> np.testing.assert_equal(result, 2)
    >>> result = next_power2(7)
    >>> np.testing.assert_equal(result, 8)
    >>> result = next_power2(9)
    >>> np.testing.assert_equal(result, 16)
    >>> result = next_power2(16)
    >>> np.testing.assert_equal(result, 16)
    """
    # return math.pow(2, math.ceil(math.log2(x)))
    return int(2 ** np.ceil(np.log2(x)))


def complex_mul(x, y):
    """
    Multiply arrays of complex numbers (it also handles
    multidimensional arrays of complex numbers). Each complex
    number is expressed as a pair of real and imaginary parts.

    :param x: the first array of complex numbers
    :param y: the second array complex numbers
    :return: result of multiplication (an array with complex numbers)
    # based on the paper: Fast Algorithms for Convolutional Neural
    Networks (https://arxiv.org/pdf/1509.09308.pdf)

    >>> # complex multiply for 2D (complex) tensors
    >>> x = tensor([[[[1., 2.], [5., 5.]], [[2., 1.], [3., 3.]]]])
    >>> y = tensor([[[[2., 3.], [-1., 2.]], [[0.0, 2.0], [2., 1.]]]])
    >>> xy = complex_mul(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[[[-4., 7.], [-15., 5.0]],
    ... [[-2., 4.0], [3.0, 9.]]]]))

    >>> x = tensor([[ 6.,  0.], [0., -2.], [1., 0.], [ 1.,  1.],
    ... [1., 2.]])
    >>> y = tensor([[2.,  0.], [0., -6.], [0., 1.], [ 1.,  1.],
    ... [2., 3.]])
    >>> np.testing.assert_array_equal(complex_mul(x, y),
    ... tensor([[12.,   0.], [-12., 0.], [0., 1.], [ 0.,   2.],
    ... [-4., 7.]]))
    >>> # x = torch.rfft(torch.tensor([1., 2., 3., 0.]), 1)
    >>> x = tensor([[ 6.,  0.], [-2., -2.], [ 2.,  0.]])
    >>> # y = torch.rfft(torch.tensor([5., 6., 7., 0.]), 1)
    >>> y = tensor([[18.,  0.], [-2., -6.], [ 6.,  0.]])
    >>> # torch.equal(tensor1, tensor2): True if two tensors
    >>> # have the same size and elements, False otherwise.
    >>> np.testing.assert_array_equal(complex_mul(x, y),
    ... tensor([[108.,   0.], [ -8.,  16.], [ 12.,   0.]]))

    >>> x = tensor([[1., 2.]])
    >>> y = tensor([[2., 3.]])
    >>> xy = complex_mul(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[-4., 7.]]))

    >>> x = tensor([[5., 5.]])
    >>> y = tensor([[-1., 2.]])
    >>> xy = complex_mul(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[-15., 5.]]))

    >>> x = tensor([[5., 5.]])
    >>> y = tensor([[-1., 2.]])
    >>> xy = complex_mul(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[-15., 5.]]))

    >>> x = tensor([[[1., 2.]]])
    >>> y = tensor([[[2., 3.]]])
    >>> xy = complex_mul(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[[-4., 7.]]]))
    >>> x = tensor([[[1., 2.], [3., 1.]]])
    >>> y = tensor([[[2., 3.], [1., 2.]]])
    >>> xy = complex_mul(x, y)
    >>> np.testing.assert_array_equal(xy,
    ... tensor([[[-4., 7.], [1., 7.]]]))
    >>> x = tensor([[[1., 2.], [3., 1.]], [[ 6.,  0.], [-2., -2.]]])
    >>> y = tensor([[[2., 3.], [1., 2.]], [[18.,  0.], [-2., -6.]]])
    >>> xy = complex_mul(x, y)
    >>> np.testing.assert_array_equal(xy,
    ... tensor([[[-4., 7.], [1., 7.]], [[108.,   0.], [ -8.,  16.]]]))
    """
    # mul = torch.mul
    # add = torch.add
    cat = torch.cat

    # ua = x.narrow(dim=-1, start=0, length=1)
    ua = x[..., :1]
    # ud = x.narrow(-1, 1, 1)
    ud = x[..., 1:]
    # va = y.narrow(-1, 0, 1)
    va = y[..., :1]
    # vb = y.narrow(-1, 1, 1)
    vb = y[..., 1:]
    ub = ua + ud
    uc = ud - ua
    vc = va + vb
    uavc = ua * vc
    # relational part of the complex number
    # result_rel = add(uavc, mul(mul(ub, vb), -1))
    result_rel = uavc - ub * vb
    # imaginary part of the complex number
    result_im = uc * va + uavc
    # use the last dimension: dim=-1
    result = cat(tensors=(result_rel, result_im), dim=-1)
    return result


def complex_mul2(x, y):
    """
    Simply multiplication of complex numbers (it also handles
    multidimensional arrays of complex numbers). Each complex
    number is expressed as a pair of real and imaginary parts.

    :param x: the first array of complex numbers
    :param y: the second array complex numbers
    :return: result of multiplication (an array with complex numbers)
    # based on the paper: Fast Algorithms for Convolutional Neural
    Networks (https://arxiv.org/pdf/1509.09308.pdf)

    >>> # complex multiply for 2D (complex) tensors
    >>> x = tensor([[[[1., 2.], [5., 5.]], [[2., 1.], [3., 3.]]]])
    >>> y = tensor([[[[2., 3.], [-1., 2.]], [[0.0, 2.0], [2., 1.]]]])
    >>> xy = complex_mul2(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[[[-4., 7.], [-15., 5.0]],
    ... [[-2., 4.0], [3.0, 9.]]]]))

    >>> x = tensor([[ 6.,  0.], [0., -2.], [1., 0.], [ 1.,  1.],
    ... [1., 2.]])
    >>> y = tensor([[2.,  0.], [0., -6.], [0., 1.], [ 1.,  1.],
    ... [2., 3.]])
    >>> np.testing.assert_array_equal(complex_mul(x, y),
    ... tensor([[12.,   0.], [-12., 0.], [0., 1.], [ 0.,   2.],
    ... [-4., 7.]]))
    >>> # x = torch.rfft(torch.tensor([1., 2., 3., 0.]), 1)
    >>> x = tensor([[ 6.,  0.], [-2., -2.], [ 2.,  0.]])
    >>> # y = torch.rfft(torch.tensor([5., 6., 7., 0.]), 1)
    >>> y = tensor([[18.,  0.], [-2., -6.], [ 6.,  0.]])
    >>> # torch.equal(tensor1, tensor2): True if two tensors
    >>> # have the same size and elements, False otherwise.
    >>> np.testing.assert_array_equal(complex_mul2(x, y),
    ... tensor([[108.,   0.], [ -8.,  16.], [ 12.,   0.]]))

    >>> x = tensor([[1., 2.]])
    >>> y = tensor([[2., 3.]])
    >>> xy = complex_mul2(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[-4., 7.]]))

    >>> x = tensor([[5., 5.]])
    >>> y = tensor([[-1., 2.]])
    >>> xy = complex_mul2(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[-15., 5.]]))

    >>> x = tensor([[5., 5.]])
    >>> y = tensor([[-1., 2.]])
    >>> xy = complex_mul2(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[-15., 5.]]))

    >>> x = tensor([[[1., 2.]]])
    >>> y = tensor([[[2., 3.]]])
    >>> xy = complex_mul2(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[[-4., 7.]]]))
    >>> x = tensor([[[1., 2.], [3., 1.]]])
    >>> y = tensor([[[2., 3.], [1., 2.]]])
    >>> xy = complex_mul2(x, y)
    >>> np.testing.assert_array_equal(xy,
    ... tensor([[[-4., 7.], [1., 7.]]]))
    >>> x = tensor([[[1., 2.], [3., 1.]], [[ 6.,  0.], [-2., -2.]]])
    >>> y = tensor([[[2., 3.], [1., 2.]], [[18.,  0.], [-2., -6.]]])
    >>> xy = complex_mul2(x, y)
    >>> np.testing.assert_array_equal(xy,
    ... tensor([[[-4., 7.], [1., 7.]], [[108.,   0.], [ -8.,  16.]]]))
    >>> del x
    >>> del y
    """
    # mul = torch.mul
    # add = torch.add
    cat = torch.cat

    # x = a + bi
    # y = c + di
    # x * y = (ac - bd) + i(ad + bc)
    a = x[..., :1]
    b = x[..., 1:]
    c = y[..., :1]
    d = y[..., 1:]

    # relational part of the complex number
    # result_rel = add(uavc, mul(mul(ub, vb), -1))
    result_rel = a * c - b * d
    # imaginary part of the complex number
    result_im = a * d + b * c
    # use the last dimension: dim=-1
    result = cat(tensors=(result_rel, result_im), dim=-1)
    return result


def pytorch_conjugate(x):
    """
    Conjugate all the complex numbers in tensor x (not in place, clone x).

    :param x: PyTorch tensor with complex numbers
    :return: conjugated numbers in x

    >>> x = tensor([[1, 2]])
    >>> x = pytorch_conjugate(x)
    >>> np.testing.assert_array_equal(x, tensor([[1, -2]]))
    >>> x = tensor([[1, 2], [3, 4]])
    >>> x = pytorch_conjugate(x)
    >>> np.testing.assert_array_equal(x, tensor([[1, -2], [3, -4]]))
    >>> x = tensor([[[1, 2], [3, 4]], [[0.0, 0.0], [0., 1.]]])
    >>> x = pytorch_conjugate(x)
    >>> np.testing.assert_array_equal(x,
    ... tensor([[[1, -2], [3, -4]], [[0., 0.], [0., -1]]]))

    >>> # conjugate 2D
    >>> x = tensor([[1, 2], [3, 4]])
    >>> x = pytorch_conjugate(x)
    >>> np.testing.assert_array_equal(x, tensor([[1, -2], [3, -4]]))

    >>> # conjugate 2D - these are complex numbers
    >>> x = tensor([[[[1, 2], [3, 4], [5, 6]], [[3,2], [1, 0], [0, 3]],
    ... [[1, 2], [8, 9], [10, 121]]]])
    >>> x = pytorch_conjugate(x)
    >>> np.testing.assert_array_equal(x, tensor([[[[1, -2], [3, -4], [5, -6]],
    ... [[3, -2], [1, 0], [0, -3]], [[1, -2], [8, -9], [10, -121]]]]))
    >>> del x
    """
    con_x = x.clone()
    con_x.narrow(dim=-1, start=1, length=1).mul_(-1)
    return con_x


def get_full_energy(x):
    """
    Return the full energy of the signal. The energy E(xfft) of a
    sequence xfft is defined as the sum of energies
    (squares of the amplitude |x|) at every point of the sequence.

    see: http://www.cs.cmu.edu/~christos/PUBLICATIONS.OLDER/
    sigmod94.pdf (equation 7)

    :param x: an array of complex numbers
    :return: the full energy of signal x

    >>> x = torch.tensor([1.2, 1.0])
    >>> full_energy, squared = get_full_energy(x)
    >>> np.testing.assert_almost_equal(full_energy, 2.4400, decimal=4)
    >>> np.testing.assert_array_almost_equal(squared, torch.tensor([2.4400]))

    >>> x_torch = torch.tensor([[1.2, 1.0], [0.5, 1.4]])
    >>> # change the x_torch to a typical numpy array with complex numbers; compare the results from numpy and pytorch
    >>> x_numpy = x_torch[...,0].numpy() + 1.0j * x_torch[...,1].numpy()
    >>> full_energy, squared = get_full_energy(x_torch)
    >>> expected_squared = np.power(np.absolute(np.array(x_numpy)), 2)
    >>> expected_full_energy = np.sum(expected_squared)
    >>> np.testing.assert_almost_equal(full_energy, expected_full_energy, decimal=4)
    >>> np.testing.assert_array_almost_equal(squared, expected_squared, decimal=4)

    >>> x_torch = torch.tensor([[-10.0, 1.5], [2.5, 1.8], [1.0, -9.0]])
    >>> # change the x_torch to a typical numpy array with complex numbers; compare the results from numpy and pytorch
    >>> x_numpy = x_torch[...,0].numpy() + 1.0j * x_torch[...,1].numpy()
    >>> full_energy, squared = get_full_energy(x_torch)
    >>> expected_squared = np.power(np.absolute(np.array(x_numpy)), 2)
    >>> expected_full_energy = np.sum(expected_squared)
    >>> np.testing.assert_almost_equal(full_energy, expected_full_energy, decimal=4)
    >>> np.testing.assert_array_almost_equal(squared, expected_squared, decimal=4)
    """
    # the signal in frequency domain is symmetric and pytorch already
    # discards second half of the signal
    squared = torch.add(torch.pow(x.narrow(-1, 0, 1), 2),
                        torch.pow(x.narrow(-1, 1, 1), 2)).squeeze()
    # sum of squared values of the signal
    full_energy = torch.sum(squared).item()
    return full_energy, squared


def get_full_energy_simple(x):
    """
    Return the full energy of the signal. The energy E(xfft) of a
    sequence xfft is defined as the sum of energies
    (squares of the amplitude |x|) at every point of the sequence.

    see: http://www.cs.cmu.edu/~christos/PUBLICATIONS.OLDER/
    sigmod94.pdf (equation 7)

    :param x: an array of complex numbers
    :return: the full energy of signal x

    >>> # Add channels.
    >>> x_torch = torch.tensor([[[-10.0, 1.5], [2.5, 1.8], [1.0, -9.0]],
    ... [[-1.0, 2.5], [3.5, -0.1], [1.2, -9.5]]])
    >>> # change the x_torch to a typical numpy array with complex numbers;
    >>> # compare the results from numpy and pytorch
    >>> x_numpy = x_torch[...,0].numpy() + 1.0j * x_torch[...,1].numpy()
    >>> full_energy, squared = get_full_energy_simple(x_torch)
    >>> expected_squared = np.power(np.absolute(np.array(x_numpy)), 2)
    >>> expected_full_energy = np.sum(expected_squared)
    >>> np.testing.assert_almost_equal(full_energy, expected_full_energy,
    ... decimal=4)
    >>> np.testing.assert_array_almost_equal(squared, expected_squared,
    ... decimal=4)

    >>> x = torch.tensor([1.2, 1.0])
    >>> full_energy, squared = get_full_energy_simple(x)
    >>> np.testing.assert_almost_equal(full_energy, 2.4400, decimal=4)
    >>> np.testing.assert_array_almost_equal(squared, torch.tensor([2.4400]))

    >>> x_torch = torch.tensor([[1.2, 1.0], [0.5, 1.4]])
    >>> # change the x_torch to a typical numpy array with complex numbers; compare the results from numpy and pytorch
    >>> x_numpy = x_torch[...,0].numpy() + 1.0j * x_torch[...,1].numpy()
    >>> full_energy, squared = get_full_energy_simple(x_torch)
    >>> expected_squared = np.power(np.absolute(np.array(x_numpy)), 2)
    >>> expected_full_energy = np.sum(expected_squared)
    >>> np.testing.assert_almost_equal(full_energy, expected_full_energy, decimal=4)
    >>> np.testing.assert_array_almost_equal(squared, expected_squared, decimal=4)

    >>> x_torch = torch.tensor([[-10.0, 1.5], [2.5, 1.8], [1.0, -9.0]])
    >>> # change the x_torch to a typical numpy array with complex numbers;
    >>> # compare the results from numpy and pytorch
    >>> x_numpy = x_torch[...,0].numpy() + 1.0j * x_torch[...,1].numpy()
    >>> full_energy, squared = get_full_energy_simple(x_torch)
    >>> expected_squared = np.power(np.absolute(np.array(x_numpy)), 2)
    >>> expected_full_energy = np.sum(expected_squared)
    >>> np.testing.assert_almost_equal(full_energy, expected_full_energy, decimal=4)
    >>> np.testing.assert_array_almost_equal(squared, expected_squared, decimal=4)

    """
    # print(x[..., 0])
    # print(x[..., 1])
    # The signal in frequency domain is symmetric and pytorch already
    # discards second half of the signal.
    squared = torch.add(torch.pow(x[..., 0], 2),
                        torch.pow(x[..., 1], 2)).squeeze()
    # sum of squared values of the signal
    full_energy = torch.sum(squared).item()
    return full_energy, squared


def get_full_energy_bulk(x):
    """
    Return the full energy of the signals. The energy E(xfft) of a
    sequence xfft is defined as the sum of energies
    (squares of the amplitude |x|) at every point of the sequence.

    see: http://www.cs.cmu.edu/~christos/PUBLICATIONS.OLDER/
    sigmod94.pdf (equation 7)

    :param x: an array of complex numbers
    :return: the full energy of signal x

    >>> # Add channels.
    >>> x_torch = torch.tensor([[[-10.0, 1.5], [2.5, 1.8], [1.0, -9.0]],
    ... [[-1.0, 2.5], [3.5, -0.1], [1.2, -9.5]]])
    >>> # change the x_torch to a typical numpy array with complex numbers;
    >>> # compare the results from numpy and pytorch
    >>> full_energy, squared = get_full_energy_bulk(x_torch)
    >>> x_numpy = x_torch[...,0].numpy() + 1.0j * x_torch[...,1].numpy()
    >>> # print("x_numpy: ", x_numpy)
    >>> expected_squared = np.power(np.absolute(np.array(x_numpy)), 2)
    >>> expected_full_energy = np.sum(expected_squared, axis=-1)
    >>> # print("expected_full_energy: ", expected_full_energy)
    >>> expected_full_energy = np.expand_dims(expected_full_energy, axis=1)
    >>> np.testing.assert_almost_equal(full_energy, expected_full_energy,
    ... decimal=4)
    >>> np.testing.assert_array_almost_equal(squared, expected_squared,
    ... decimal=4)

    >>> x = torch.tensor([1.2, 1.0])
    >>> full_energy, squared = get_full_energy_bulk(x)
    >>> np.testing.assert_almost_equal(full_energy, 2.4400, decimal=4)
    >>> np.testing.assert_array_almost_equal(squared, torch.tensor([2.4400]))

    >>> x_torch = torch.tensor([[1.2, 1.0], [0.5, 1.4]])
    >>> # change the x_torch to a typical numpy array with complex numbers; compare the results from numpy and pytorch
    >>> full_energy, squared = get_full_energy_bulk(x_torch)
    >>> x_numpy = x_torch[...,0].numpy() + 1.0j * x_torch[...,1].numpy()
    >>> expected_squared = np.power(np.absolute(np.array(x_numpy)), 2)
    >>> expected_full_energy = np.sum(expected_squared)
    >>> np.testing.assert_almost_equal(full_energy, expected_full_energy, decimal=4)
    >>> np.testing.assert_array_almost_equal(squared, expected_squared, decimal=4)

    >>> x_torch = torch.tensor([[-10.0, 1.5], [2.5, 1.8], [1.0, -9.0]])
    >>> # change the x_torch to a typical numpy array with complex numbers;
    >>> # compare the results from numpy and pytorch
    >>> full_energy, squared = get_full_energy_bulk(x_torch)
    >>> x_numpy = x_torch[...,0].numpy() + 1.0j * x_torch[...,1].numpy()
    >>> expected_squared = np.power(np.absolute(np.array(x_numpy)), 2)
    >>> expected_full_energy = np.sum(expected_squared)
    >>> np.testing.assert_almost_equal(full_energy, expected_full_energy, decimal=4)
    >>> np.testing.assert_array_almost_equal(squared, expected_squared, decimal=4)

    """
    # print(x[..., 0])
    # print(x[..., 1])
    # The signal in frequency domain is symmetric and pytorch already
    # discards second half of the signal.
    real_squared = torch.pow(x[..., 0], 2)
    img_squared = torch.pow(x[..., 1], 2)
    squared = torch.add(real_squared, img_squared)
    # sum of squared values of the signal
    full_energy = torch.sum(squared, dim=-1, keepdim=True)
    return full_energy, squared


def preserve_energy_index(xfft, energy_rate=None, index_back=None):
    """
    To which index should we preserve the xfft signal (and discard
    the remaining coefficients). This is based on the provided
    energy_rate, or if the energy_rate is not provided, then
    index_back is applied.

    :param xfft: the input signal to be truncated
    :param energy_rate: how much energy should we preserve in the xfft signal
    :param index_back: how many coefficients of xfft should we discard counting from the back of the xfft
    :return: calculated index, no truncation applied to xfft itself, returned at least the index of first coefficient
    >>> xfft = torch.tensor([])
    >>> result = preserve_energy_index(xfft, energy_rate=1.0)
    >>> np.testing.assert_equal(result, None)

    >>> xfft = torch.tensor([[1., 2.], [3., 4.], [0.1, 0.1]])
    >>> result = preserve_energy_index(xfft, energy_rate=1.0)
    >>> np.testing.assert_equal(result, 3)

    >>> xfft = [[1., 2.], [3., 4.]]
    >>> result = preserve_energy_index(xfft)
    >>> np.testing.assert_equal(result, 2)

    >>> xfft = [[1., 2.], [3., 4.], [5., 6.]]
    >>> result = preserve_energy_index(xfft, index_back=1)
    >>> np.testing.assert_equal(result, 2)

    >>> xfft = torch.tensor([[1., 2.], [3., 4.], [0.1, 0.1]])
    >>> result = preserve_energy_index(xfft, energy_rate=0.9)
    >>> np.testing.assert_equal(result, 2)

    >>> xfft = torch.tensor([[3., 10.], [1., 1.], [0.1, 0.1]])
    >>> result = preserve_energy_index(xfft, energy_rate=0.5)
    >>> np.testing.assert_equal(result, 1)

    >>> xfft = torch.tensor([[3., 10.], [1., 1.], [0.1, 0.1]])
    >>> result = preserve_energy_index(xfft, energy_rate=0.0)
    >>> np.testing.assert_equal(result, 1)

    >>> x_torch = torch.tensor([[3., 10.], [1., 1.], [0.1, 0.1]])
    >>> x_numpy = x_torch[...,0].numpy() + 1.0j * x_torch[...,1].numpy()
    >>> squared_numpy = np.power(np.absolute(np.array(x_numpy)), 2)
    >>> full_energy_numpy = np.sum(squared_numpy)
    >>> # set energy rate to preserve only the first and second
    >>> # coefficients
    >>> energy_rate = squared_numpy[0]/full_energy_numpy + 0.0001
    >>> result = preserve_energy_index(x_torch,
    ... energy_rate=energy_rate)
    >>> np.testing.assert_equal(result, 2)
    >>> # set energy rate to preserved only the first coefficient
    >>> energy_rate = squared_numpy[0]/full_energy_numpy - 0.0001
    >>> result = preserve_energy_index(x_torch,
    ... energy_rate=energy_rate)
    >>> np.testing.assert_equal(result, 1)
    """
    if xfft is None or len(xfft) == 0:
        return None
    if energy_rate is not None:
        full_energy, squared = get_full_energy(xfft)
        current_energy = 0.0
        preserved_energy = full_energy * energy_rate
        index = 0
        while current_energy < preserved_energy and index < len(squared):
            current_energy += squared[index]
            index += 1
        return max(index, 1)
    elif index_back is not None:
        return len(xfft) - index_back
    return len(xfft)


def preserve_energy_index_back(xfft, preserve_energy=None):
    """
    Give index_back for the given energy rate.

    :param xfft: the input fft-ed signal
    :param energy_rate: how much energy of xfft should be preserved?
    :return: the index back (how many coefficient from the end of the signal
    should be discarded?

    >>> xfft = torch.tensor([[
    ... [[5, 6], [3, 4], [1, 2]], [[0, 1], [1, 0], [2, 2]]],
    ... [[[-1, 3], [1, 0], [0, 2]], [[1, 1], [1, -2], [3, 2]]]])
    >>> index_back = preserve_energy_index_back(xfft, 50)
    >>> np.testing.assert_equal(index_back, 2)

    """
    # The second dimension from the end is the length because this is a complex
    # signal.
    input_length = xfft.shape[-2]
    if xfft is None or len(xfft) == 0:
        return 0
    squared = torch.add(torch.pow(xfft[..., 0], 2),
                        torch.pow(xfft[..., 1], 2))
    # Sum the batch and channel dimensions (we first reduce to many channels -
    # first 0, and then to only a single channel - next 0 (the dimensions
    # collapse one by one).
    squared = squared.sum(dim=0).sum(dim=0)
    assert len(squared) == input_length
    # Sum of squared values of the signal of length input_length.
    full_energy = torch.sum(squared).item()
    current_energy = 0.0
    preserved_energy = full_energy * preserve_energy / 100.0
    index = 0
    # Accumulate the energy (and increment the index) until the required
    # preserved energy is reached.
    while current_energy < preserved_energy and index < input_length:
        current_energy += squared[index]
        index += 1
    return input_length - index


def correlate_signals(x, y, fft_size, out_size, preserve_energy_rate=None,
                      index_back=None, signal_ndim=1):
    """
    Cross-correlation of the signals: x and y.
    Theory: X(f) = fft(x(t)). The first sample X(0) of the
    transformed series is the DC component, more commonly known
    as the average of the input series. For the normalized fft
    (both sums are multiplied by $\frac{1}{\sqrt{N}}$. The length of the sin(x)
    is || sin(x)||^2 = \integral_{0}^{2\pi} sin^2(x) dx = \pi, so
    ||sin(x)||=\sqrt(\pi)

    $$
    \begin{align}
        X(0) = \frac{1}{\sqrt{N}} \sum_{n=0}^{n=N-1} x(n)
    \end{align}
    $$

    :param x: input signal
    :param y: filter
    :param fft_size: the size of the signal in the frequency domain
    :param out_size: required output len (size)
    :param preserve_energy_rate: compressed to this energy rate
    :param index_back: how many coefficients to remove
    :param signal_ndim: what is the dimension of the input data
    :return: output signal after correlation of signals x and y

    >>> x = tensor([[[1.0,2.0,3.0,4.0], [1.0,0.0,4.0,4.0]]])
    >>> # x.shape is torch.Size([1, 2, 4])
    >>> # two filters
    >>> y = tensor([[[1.0,3.0], [1.0,3.0]], [[2.0,1.0], [0.0,1.0]]])
    >>> # y.shape is torch.Size([2, 2, 2])
    >>> # W - width of input signals (time-series)
    >>> W = x.shape[-1]
    >>> # WW - width of the filter
    >>> WW = y.shape[-1]
    >>> out_size = W - WW + 1
    >>> result = correlate_signals(x=x, y=y, fft_size=W, out_size=out_size)
    >>> # print("result: ", result)
    >>> expected = np.array([[[7.0, 11.0, 15.0], [1.0, 12.0, 16.0]],
    ... [[4.0, 7.0, 10.0], [0.0, 4.0, 4.0]]])
    >>> np.testing.assert_array_almost_equal(result, expected)

    >>> x = tensor([[[1.0,2.0,3.0,4.0], [1.0,2.0,3.0,4.0]]])
    >>> y = tensor([[[1.0,3.0], [1.0,3.0]]])
    >>> result = correlate_signals(x=x, y=y, fft_size=x.shape[-1],
    ... out_size=(x.shape[-1]-y.shape[-1] + 1))
    >>> np.testing.assert_array_almost_equal(result,
    ... np.array([[[7.0, 11.0, 15.0], [7.0, 11.0, 15.0]]]))

    >>> x = tensor([1.0,2.0,3.0,4.0])
    >>> y = tensor([1.0,3.0])
    >>> result = correlate_signals(x=x, y=y, fft_size=len(x), out_size=(len(x)-len(y) + 1))
    >>> expected_result = np.correlate(x, y, mode='valid')
    >>> np.testing.assert_array_almost_equal(result, expected_result)

    >>> x = torch.from_numpy(np.random.rand(10))
    >>> y = torch.from_numpy(np.random.rand(3))
    >>> result = correlate_signals(x=x, y=y, fft_size=len(x), out_size=(len(x)-len(y) + 1))
    >>> expected_result = np.correlate(x, y, mode='valid')
    >>> np.testing.assert_array_almost_equal(result, expected_result)

    >>> x = torch.from_numpy(np.random.rand(100))
    >>> y = torch.from_numpy(np.random.rand(11))
    >>> result = correlate_signals(x=x, y=y, fft_size=len(x), out_size=(len(x)-len(y) + 1))
    >>> expected_result = np.correlate(x, y, mode='valid')
    >>> np.testing.assert_array_almost_equal(result, expected_result)

    >>> x = tensor([[[1.0,2.0,3.0,4.0]]])
    >>> y = tensor([[[1.0,3.0]]])
    >>> s = x.shape[-1]- y.shape[-1] + 1
    >>> result = correlate_signals(x=x, y=y, fft_size=x.shape[-1], out_size=s)
    >>> expect = np.array([[[7.0, 11.0, 15.0]]])
    >>> np.testing.assert_array_almost_equal(result, expect)
    """
    # pad the signals to the fft size
    x = F.pad(x, (0, fft_size - x.shape[-1]), 'constant', 0.0)
    y = F.pad(y, (0, fft_size - y.shape[-1]), 'constant', 0.0)
    # onesided=True: only the frequency coefficients to the Nyquist
    # frequency are retained (about half the length of the
    # input signal) so the original signal can be still exactly
    # reconstructed from the frequency samples.
    xfft = torch.rfft(x, signal_ndim=signal_ndim, onesided=True)
    yfft = torch.rfft(y, signal_ndim=signal_ndim, onesided=True)
    if preserve_energy_rate is not None or index_back is not None:
        index_xfft = preserve_energy_index(xfft, preserve_energy_rate,
                                           index_back)
        index_yfft = preserve_energy_index(yfft, preserve_energy_rate,
                                           index_back)
        index = max(index_xfft, index_yfft)
        # with open(log_file, "a+") as f:
        #     f.write("index: " + str(index_back) +
        # ";preserved energy input: " + str(
        #         compute_energy(xfft[:index]) / compute_energy(
        # xfft[:fft_size // 2 + 1])) +
        #             ";preserved energy filter: " + str(
        #         compute_energy(yfft[:index]) / compute_energy(
        # yfft[:fft_size // 2 + 1])) + "\n")

        # complex numbers are represented as the pair of numbers in
        # the last dimension so we have to narrow the length
        # of the last but one dimension
        xfft = xfft.narrow(dim=-2, start=0, length=index)
        yfft = yfft.narrow(dim=-2, start=0, length=index)
        # print("the signal size after compression: ", index)

        input = complex_mul(xfft, pytorch_conjugate(yfft))
        # we need to pad complex numbers expressed as a pair of real
        # numbers in the last dimension
        # xfft = F.pad(input=xfft, pad=(0, fft_size - index),
        # mode='constant', value=0)
        # yfft = F.pad(input=yfft, pad=(0, fft_size - index),
        # mode='constant', value=0)
        pad_shape = tensor(xfft.shape)
        # xfft has at least two dimension (with the last one being a
        # dimension for a pair of real number representing a complex
        # number.
        pad_shape[-2] = (fft_size // 2 + 1) - index
        complex_pad = torch.zeros(*pad_shape, dtype=xfft.dtype,
                                  device=xfft.device)
        input = torch.cat((input, complex_pad), dim=-2)
    else:
        input = complex_mul(xfft, pytorch_conjugate(yfft))
    out = torch.irfft(input, signal_ndim=signal_ndim,
                      signal_sizes=(x.shape[-1],))

    # plot_signal(out, "out after ifft")
    out = out[..., :out_size]
    # plot_signal(out, "after truncating to xlen: " + str(x_len))

    # sum the values across the computed layers (for each filter)
    # out = torch.sum(out, dim=-2, keepdim=True)
    return out


def correlate_fft_signals(xfft, yfft, fft_size: int,
                          signal_ndim: int = 1) -> object:
    """
    Similar to 'correlate_signal' function but the signals are provided in the
    frequency domain (after fft) for the reuse of the maps.

    Cross-correlation of the signals: x and y.
    Theory: X(f) = fft(x(t)). The first sample X(0) of the
    transformed series is the DC component, more commonly known
    as the average of the input series. For the normalized fft
    (both sums are multiplied by $\frac{1}{\sqrt{N}}$. The length of the sin(x)
    is || sin(x)||^2 = \integral_{0}^{2\pi} sin^2(x) dx = \pi, so
    ||sin(x)||=\sqrt(\pi)

    $$
    \begin{align}
        X(0) = \frac{1}{\sqrt{N}} \sum_{n=0}^{n=N-1} x(n)
    \end{align}
    $$

    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # complex_mul only broadcasts the input if we provide all filters
    # but staying on this level is probably more performant than the other
    # approach (with full broadcast of the input and output) since we use less
    # memory.
    # >>> x = tensor([[[1.0,2.0,3.0,4.0], [1.0,3.0,3.0,2.0]],
    # ... [[2.0,1.0,3.0,5.0], [1.0,2.0,5.0,1.0]]])
    # >>> # two filters
    # >>> y = tensor([[[1.0,3.0], [0.0,3.0]], [[1.0,1.0], [2.0,2.0]]])
    # >>> fft_size = x.shape[-1]
    # >>> y_padded = F.pad(y, (0, fft_size - y.shape[-1]), 'constant', 0.0)
    # >>> signal_ndim = 1
    # >>> onesided = True
    # >>> xfft = torch.rfft(x, signal_ndim=signal_ndim, onesided=onesided)
    # >>> yfft = torch.rfft(y_padded, signal_ndim=signal_ndim, onesided=onesided)
    # >>> result = correlate_fft_signals(xfft=xfft, yfft=yfft,
    # ... fft_size=x.shape[-1], out_size=(x.shape[-1]-y.shape[-1] + 1),
    # ... input_size=x.shape[-1])
    # >>> # print("result: ", result)
    # >>> np.testing.assert_array_almost_equal(result,
    # ... np.array([[[16.0, 20.0, 21.0], [11.0, 17.0, 17.0]],
    # ... [[11.0, 25.0, 21.0], [9.0, 18.0, 20.0]]]))
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    >>> # Test the backward computation without summing up the final tensor.
    >>> # The summing up of the final tensor is done only if param is_forward
    >>> # is set to True.
    >>> x = tensor([[[1.0, 2.0, 3.0], [-1.0, -3.0, 2.0]]])
    >>> # Two filters.
    >>> y = tensor([[[0.1, -0.2]]])
    >>> fft_size = x.shape[-1]
    >>> y_padded = F.pad(y, (0, fft_size - y.shape[-1]), 'constant', 0.0)
    >>> signal_ndim = 1
    >>> onesided = True
    >>> xfft = torch.rfft(x, signal_ndim=signal_ndim, onesided=onesided)
    >>> yfft = torch.rfft(y_padded, signal_ndim=signal_ndim, onesided=onesided)
    >>> result = correlate_fft_signals(xfft=xfft, yfft=yfft,
    ... fft_size=x.shape[-1])
    >>> # print("result: ", result)
    >>> out_size=(x.shape[-1]-y.shape[-1] + 1)
    >>> np.testing.assert_array_almost_equal(result[...,:out_size],
    ... np.array([[[-0.3, -0.4], [ 0.5, -0.7]]]))

    >>> x = tensor([[[2.0,1.0,3.0,5.0], [1.0,2.0,5.0,1.0]]])
    >>> # two filters
    >>> y = tensor([[[1.0,3.0], [0.0,3.0]], [[1.0,1.0], [2.0,2.0]]])
    >>> fft_size = x.shape[-1]
    >>> y_padded = F.pad(y, (0, fft_size - y.shape[-1]), 'constant', 0.0)
    >>> signal_ndim = 1
    >>> onesided = True
    >>> xfft = torch.rfft(x, signal_ndim=signal_ndim, onesided=onesided)
    >>> yfft = torch.rfft(y_padded, signal_ndim=signal_ndim, onesided=onesided)
    >>> result = correlate_fft_signals(xfft=xfft, yfft=yfft,
    ... fft_size=x.shape[-1])
    >>> # print("result: ", result)
    >>> out_size=(x.shape[-1]-y.shape[-1] + 1)
    >>> np.testing.assert_array_almost_equal(result[..., :out_size],
    ... np.array([[[ 5., 10., 18.], [ 6., 15.,  3.]],
    ... [[ 3.,  4.,  8.], [ 6., 14., 12.]]]))

    >>> x = tensor([[[1.0,2.0,3.0,4.0], [1.0,3.0,3.0,2.0]]])
    >>> # two filters
    >>> y = tensor([[[1.0,3.0], [0.0,3.0]], [[1.0,1.0], [2.0,2.0]]])
    >>> fft_size = x.shape[-1]
    >>> y_padded = F.pad(y, (0, fft_size - y.shape[-1]), 'constant', 0.0)
    >>> signal_ndim = 1
    >>> onesided = True
    >>> xfft = torch.rfft(x, signal_ndim=signal_ndim, onesided=onesided)
    >>> yfft = torch.rfft(y_padded, signal_ndim=signal_ndim, onesided=onesided)
    >>> result = correlate_fft_signals(xfft=xfft, yfft=yfft,
    ... fft_size=x.shape[-1])
    >>> # print("result: ", result)
    >>> out_size=(x.shape[-1]-y.shape[-1] + 1)
    >>> np.testing.assert_array_almost_equal(result[..., :out_size],
    ... np.array([[[ 7., 11., 15.], [ 9.,  9.,  6.]],
    ... [[ 3.,  5.,  7.], [ 8., 12., 10.]]]))

    >>> # 1 signal in the batch, 2 channels, signal of length 3
    >>> x = tensor([[[1.0,2.0,3.0,4.0], [1.0,2.0,3.0,4.0]]])
    >>> y = tensor([[[1.0,3.0], [1.0,3.0]]])
    >>> fft_size = x.shape[-1]
    >>> y_padded = F.pad(y, (0, fft_size - y.shape[-1]), 'constant', 0.0)
    >>> signal_ndim = 1
    >>> onesided = True
    >>> xfft = torch.rfft(x, signal_ndim=signal_ndim, onesided=onesided)
    >>> yfft = torch.rfft(y_padded, signal_ndim=signal_ndim, onesided=onesided)
    >>> result = correlate_fft_signals(xfft=xfft, yfft=yfft,
    ... fft_size=x.shape[-1])
    >>> # print("result: ", result)
    >>> out_size=(x.shape[-1]-y.shape[-1] + 1)
    >>> np.testing.assert_array_almost_equal(result[..., :out_size],
    ... np.array([[[ 7., 11., 15.], [ 7., 11., 15.]]]))

    >>> x = tensor([1.0,2.0,3.0,4.0])
    >>> y = tensor([1.0,3.0])
    >>> fft_size = x.shape[-1]
    >>> y_padded = F.pad(y, (0, fft_size - y.shape[-1]), 'constant', 0.0)
    >>> signal_ndim = 1
    >>> onesided = True
    >>> xfft = torch.rfft(x, signal_ndim=signal_ndim, onesided=onesided)
    >>> yfft = torch.rfft(y_padded, signal_ndim=signal_ndim, onesided=onesided)
    >>> result = correlate_fft_signals(xfft=xfft, yfft=yfft, fft_size=len(x))
    >>> out_size=len(x)-len(y) + 1
    >>> np.testing.assert_array_almost_equal(result[..., :out_size],
    ... np.array([7.0, 11.0, 15.0]))

    >>> x = torch.from_numpy(np.random.rand(10))
    >>> y = torch.from_numpy(np.random.rand(3))
    >>> fft_size = x.shape[-1]
    >>> y_padded = F.pad(y, (0, fft_size - y.shape[-1]), 'constant', 0.0)
    >>> # print("y_padded: ", y_padded)
    >>> signal_ndim = 1
    >>> onesided = True
    >>> xfft = torch.rfft(x, signal_ndim=signal_ndim, onesided=onesided)
    >>> yfft = torch.rfft(y_padded, signal_ndim=signal_ndim, onesided=onesided)
    >>> result = correlate_fft_signals(xfft=xfft, yfft=yfft, fft_size=len(x))
    >>> out_size=len(x)-len(y) + 1
    >>> expected_result = np.correlate(x, y, mode='valid')
    >>> np.testing.assert_array_almost_equal(result[..., :out_size],
    ... expected_result)

    >>> x = torch.from_numpy(np.random.rand(100))
    >>> y = torch.from_numpy(np.random.rand(11))
    >>> fft_size = x.shape[-1]
    >>> y_padded = F.pad(y, (0, fft_size - y.shape[-1]), 'constant', 0.0)
    >>> # print("y_padded: ", y_padded)
    >>> signal_ndim = 1
    >>> onesided = True
    >>> xfft = torch.rfft(x, signal_ndim=signal_ndim, onesided=onesided)
    >>> yfft = torch.rfft(y_padded, signal_ndim=signal_ndim, onesided=onesided)
    >>> result = correlate_fft_signals(xfft=xfft, yfft=yfft, fft_size=len(x))
    >>> out_size=x.shape[-1]-y.shape[-1] + 1
    >>> expected_result = np.correlate(x, y, mode='valid')
    >>> np.testing.assert_array_almost_equal(result[..., :out_size],
    ... expected_result)

    :param xfft: input signal after fft
    :param yfft: filter after fft
    :param fft_size: the size of the signal in the frequency domain
    :param signal_ndim: the dimension of the signal (we set it to 1)
    :return: output signal after correlation of signals xfft and yfft
    """
    # xfft = complex_pad_simple(xfft=xfft, fft_size=fft_size)
    # yfft = complex_pad_simple(xfft=yfft, fft_size=fft_size)

    freq_mul = complex_mul(xfft, pytorch_conjugate(yfft))

    freq_mul = complex_pad_simple(xfft=freq_mul, fft_size=fft_size)

    out = torch.irfft(
        input=freq_mul, signal_ndim=signal_ndim, signal_sizes=(fft_size,))
    return out


def correlate_fft_signals2D(xfft, yfft, input_height, input_width,
                            half_fft_height, half_fft_width,
                            out_height, out_width, is_forward=True):
    """
    >>> # Test 2 channels and 2 filters.
    >>> x = tensor([[[[1.0, 2.0, 3.0], [3.0, 4.0, 1.0], [1., 2., 1.]],
    ... [[1., 1., 2.], [2., 3., 1.], [2., -1., 3.]]]])
    >>> y = tensor([[[[1.0, 2.0], [3.0, 2.0]], [[-1.0, 2.0],[3.0, -2.0]]],
    ... [[[-1.0, 1.0], [2.0, 3.0]], [[-2.0, 1.0], [1.0, -3.0]]]])
    >>> fft_width = x.shape[-1]
    >>> fft_height = x.shape[-2]
    >>> pad_right = fft_width - y.shape[-1]
    >>> pad_bottom = fft_height - y.shape[-2]
    >>> y_padded = F.pad(y, (0, pad_right, 0, pad_bottom), 'constant', 0.0)
    >>> np.testing.assert_array_equal(x=tensor([
    ... [[[1.0, 2.0, 0.0], [3.0, 2.0, 0.0], [0.0, 0.0, 0.0]],
    ... [[-1.0, 2.0, 0.0], [3.0, -2.0, 0.0], [0.0, 0.0, 0.0]]],
    ... [[[-1.0, 1.0, 0.0], [2.0, 3.0, 0.0], [0.0, 0.0, 0.0]],
    ... [[-2.0, 1.0, 0.0], [1.0, -3.0, 0.0], [0.0, 0.0, 0.0]]]]), y=y_padded,
    ... err_msg="The expected result x is different than the computed y.")
    >>> signal_ndim = 2
    >>> onesided = True
    >>> xfft = torch.rfft(x, signal_ndim=signal_ndim, onesided=onesided)
    >>> yfft = torch.rfft(y_padded, signal_ndim=signal_ndim, onesided=onesided)
    >>> result = correlate_fft_signals2D(xfft=xfft, yfft=yfft,
    ... input_height=fft_height, input_width=fft_width,
    ... half_fft_height=xfft.shape[-3], half_fft_width=xfft.shape[-2],
    ... out_height=(x.shape[-2]-y.shape[-2]+1),
    ... out_width=(x.shape[-1]-y.shape[-1] + 1))
    >>> # print("result: ", result)
    >>> np.testing.assert_array_almost_equal(
    ... x=np.array([[[[23.0, 32.0], [30., 4.]],[[11.0, 12.0], [13.0, -11.0]]]]),
    ... y=result, decimal=5,
    ... err_msg="The expected array x and computed y are not almost equal.")

    >>> # Test 2D convolution.
    >>> x = tensor([[[1.0, 2.0, 3.0], [3.0, 4.0, 1.0], [1., 2., 1.]]])
    >>> # A single filter.
    >>> y = tensor([[[1.0, 2.0], [3.0, 2.0]]])
    >>> fft_width = x.shape[-1]
    >>> fft_height = x.shape[-2]
    >>> pad_right = fft_width - y.shape[-1]
    >>> pad_bottom = fft_height - y.shape[-2]
    >>> y_padded = F.pad(y, (0, pad_right, 0, pad_bottom), 'constant', 0.0)
    >>> np.testing.assert_array_equal(x=tensor([[[1.0, 2.0, 0.0],
    ... [3.0, 2.0, 0.0], [0.0, 0.0, 0.0]]]), y=y_padded,
    ... err_msg="The expected result x is different than the computed y.")
    >>> signal_ndim = 2
    >>> onesided = True
    >>> xfft = torch.rfft(x, signal_ndim=signal_ndim, onesided=onesided)
    >>> yfft = torch.rfft(y_padded, signal_ndim=signal_ndim, onesided=onesided)
    >>> result = correlate_fft_signals2D(xfft=xfft, yfft=yfft,
    ... input_height=fft_height, input_width=fft_width,
    ... half_fft_height=xfft.shape[-2], half_fft_width=xfft.shape[-1],
    ... out_height=(x.shape[-2]-y.shape[-2]+1),
    ... out_width=(x.shape[-1]-y.shape[-1] + 1))
    >>> # print("result: ", result)
    >>> np.testing.assert_array_almost_equal(
    ... x=np.array([[[22.0, 22.0], [18., 14.]]]), y=result,
    ... err_msg="The expected array x and computed y are not almost equal.")

    >>> # Test 2D convolution.
    >>> x = tensor([[[[1.0, 2.0, 3.0], [3.0, 4.0, 1.0], [1., 2., 1.]]]])
    >>> # A single filter.
    >>> y = tensor([[[[1.0, 2.0], [3.0, 2.0]]]])
    >>> fft_width = x.shape[-1]
    >>> fft_height = x.shape[-2]
    >>> pad_right = fft_width - y.shape[-1]
    >>> pad_bottom = fft_height - y.shape[-2]
    >>> y_padded = F.pad(y, (0, pad_right, 0, pad_bottom), 'constant', 0.0)
    >>> np.testing.assert_array_equal(x=tensor([[[[1.0, 2.0, 0.0],
    ... [3.0, 2.0, 0.0], [0.0, 0.0, 0.0]]]]), y=y_padded,
    ... err_msg="The expected result x is different than the computed y.")
    >>> signal_ndim = 2
    >>> onesided = True
    >>> xfft = torch.rfft(x, signal_ndim=signal_ndim, onesided=onesided)
    >>> yfft = torch.rfft(y_padded, signal_ndim=signal_ndim, onesided=onesided)
    >>> result = correlate_fft_signals2D(xfft=xfft, yfft=yfft,
    ... input_height=fft_height, input_width=fft_width,
    ... half_fft_height=xfft.shape[-3], half_fft_width=xfft.shape[-2],
    ... out_height=(x.shape[-2]-y.shape[-2]+1),
    ... out_width=(x.shape[-1]-y.shape[-1] + 1))
    >>> # print("result: ", result)
    >>> np.testing.assert_array_almost_equal(
    ... x=np.array([[[[22.0, 22.0], [18., 14.]]]]), y=result,
    ... err_msg="The expected array x and computed y are not almost equal.")

    >>> # Test 2 channels.
    >>> x = tensor([[[[1.0, 2.0, 3.0], [3.0, 4.0, 1.0], [1., 2., 1.]],
    ... [[1., 1., 2.], [2., 3., 1.], [2., -1., 3.]]]])
    >>> # A single filter.
    >>> y = tensor([[[[1.0, 2.0], [3.0, 2.0]], [[-1.0, 2.0],[3.0, -2.0]]]])
    >>> fft_width = x.shape[-1]
    >>> fft_height = x.shape[-2]
    >>> pad_right = fft_width - y.shape[-1]
    >>> pad_bottom = fft_height - y.shape[-2]
    >>> y_padded = F.pad(y, (0, pad_right, 0, pad_bottom), 'constant', 0.0)
    >>> np.testing.assert_array_equal(x=tensor([[
    ... [[1.0, 2.0, 0.0], [3.0, 2.0, 0.0], [0.0, 0.0, 0.0]],
    ... [[-1.0, 2.0, 0.0], [3.0, -2.0, 0.0], [0.0, 0.0, 0.0]]
    ... ]]), y=y_padded,
    ... err_msg="The expected result x is different than the computed y.")
    >>> signal_ndim = 2
    >>> onesided = True
    >>> xfft = torch.rfft(x, signal_ndim=signal_ndim, onesided=onesided)
    >>> yfft = torch.rfft(y_padded, signal_ndim=signal_ndim, onesided=onesided)
    >>> result = correlate_fft_signals2D(xfft=xfft, yfft=yfft,
    ... input_height=fft_height, input_width=fft_width,
    ... half_fft_height=xfft.shape[-3], half_fft_width=xfft.shape[-2],
    ... out_height=(x.shape[-2]-y.shape[-2]+1),
    ... out_width=(x.shape[-1]-y.shape[-1] + 1))
    >>> # print("result: ", result)
    >>> np.testing.assert_array_almost_equal(
    ... x=np.array([[[[23.0, 32.0], [30., 4.]]]]), y=result, decimal=5,
    ... err_msg="The expected array x and computed y are not almost equal.")

    :param xfft: first input map
    :param yfft: second input map
    :param input_height: the height of input x
    :param input_widt: the width of input x
    :param fft_height: the fft height for maps (both input maps xfft and yfft
    for cross-correlation have to have the same dimensions).
    :param fft_width: the fft width for maps (both input maps xfft and yfft
    for cross-correlation have to have the same dimensions).
    :param out_height: the height of the output map
    :param out_width: the width of the output map
    :param is_forward: is the correlation for a forward of a backward pass of
    the convolution operation.
    :return: output map after correlation of xfft with yfft
    """
    signal_ndim = 2

    xfft = complex_pad2D(fft_input=xfft, half_fft_height=half_fft_height,
                         half_fft_width=half_fft_width)
    yfft = complex_pad2D(fft_input=yfft, half_fft_height=half_fft_height,
                         half_fft_width=half_fft_width)

    freq_mul = complex_mul(xfft, pytorch_conjugate(yfft))
    out = torch.irfft(input=freq_mul, signal_ndim=signal_ndim,
                      signal_sizes=(input_height, input_width), onesided=True)

    out = out[..., :out_height, :out_width]
    if out.dim() > 2 and is_forward:
        out = torch.sum(input=out, dim=-3)
        out = torch.unsqueeze(input=out, dim=0)  # unsqueeze the channels
    return out


def complex_pad(xfft, fft_size):
    """
    >>> # Typical use case.
    >>> xfft = tensor([[[1.0, 2.0], [3.0, 4.0], [4.0, 5.0]]])
    >>> expected_xfft_pad = tensor([[[1.0, 2.0], [3.0, 4.0], [4.0, 5.0],
    ... [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]])
    >>> half_fft_size = xfft.shape[-2] + 3
    >>> fft_size = (half_fft_size - 1) * 2
    >>> xfft_pad = complex_pad(xfft, fft_size)
    >>> np.testing.assert_array_almost_equal(x=expected_xfft_pad, y=xfft_pad,
    ... err_msg="The expected x is different than computed y")

    >>> # Only two dimensions (the -2 being the "true one" and the last one is
    >>> # for the complex numbers.
    >>> xfft = tensor([[1.0, 0.0], [0.0, 4.0], [4.0, 5.0], [-1.0, 0.0]])
    >>> expected_xfft_pad = tensor([[1.0, 0.0], [0.0, 4.0], [4.0, 5.0],
    ... [-1.0, 0.0], [0.0, 0.0], [0.0, 0.0]])
    >>> half_fft_size = xfft.shape[-2] + 2
    >>> fft_size = (half_fft_size - 1) * 2
    >>> xfft_pad = complex_pad(xfft, fft_size)
    >>> np.testing.assert_array_almost_equal(x=expected_xfft_pad, y=xfft_pad,
    ... err_msg="The expected x is different than computed y")

    >>> # Check if it works for the case where padding should not be done.
    >>> # So expected result is the same as the xfft.
    >>> xfft = tensor([[[1.0, 2.0], [3.0, 4.0], [4.0, 5.0]]])
    >>> half_fft_size = xfft.shape[-2]
    >>> fft_size = (half_fft_size - 1) * 2
    >>> xfft_pad = complex_pad(xfft, fft_size)
    >>> np.testing.assert_array_almost_equal(x=xfft, y=xfft_pad,
    ... err_msg="The expected x is different than computed y")

    Pad xfft with zeros in the frequency domain to the size specified with
    fft_size.

    :param xfft: the input signal in the frequency domain (represented by
    complex numbers).
    :param fft_size: the expected (initial) fft size (used in the forward pass).
    :return: the padded xfft signal with zeros in the frequency domain.
    """
    # xfft has at least two dimensions (with the last one being a dimension for
    # a pair of real numbers representing a complex number). Moreover, pytorch
    # supports half-sized fft (one-sided fft) by default.
    half_fft = fft_size // 2 + 1
    pad_shape = tensor(xfft.shape)
    # Omit the last dimension (-1) for complex numbers.
    current_length = xfft.shape[-2]
    if current_length < half_fft:
        pad_shape[-2] = half_fft - current_length
        complex_pad = torch.zeros(*pad_shape, dtype=xfft.dtype,
                                  device=xfft.device)
        xfft = torch.cat((xfft, complex_pad), dim=-2)
    return xfft


def complex_pad_simple(xfft, fft_size):
    """
    >>> # Typical use case.
    >>> xfft = tensor([[[1.0, 2.0], [3.0, 4.0], [4.0, 5.0]]])
    >>> expected_xfft_pad = tensor([[[1.0, 2.0], [3.0, 4.0], [4.0, 5.0],
    ... [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]])
    >>> half_fft_size = xfft.shape[-2] + 3
    >>> fft_size = (half_fft_size - 1) * 2
    >>> xfft_pad_simple = complex_pad_simple(xfft, fft_size)
    >>> np.testing.assert_array_almost_equal(x=expected_xfft_pad,
    ... y=xfft_pad_simple,
    ... err_msg="The expected x is different than computed y")

    >>> # Only two dimensions (the -2 being the "true one" and the last one is
    >>> # for the complex numbers.
    >>> xfft = tensor([[1.0, 0.0], [0.0, 4.0], [4.0, 5.0], [-1.0, 0.0]])
    >>> expected_xfft_pad = tensor([[1.0, 0.0], [0.0, 4.0], [4.0, 5.0],
    ... [-1.0, 0.0], [0.0, 0.0], [0.0, 0.0]])
    >>> half_fft_size = xfft.shape[-2] + 2
    >>> fft_size = (half_fft_size - 1) * 2
    >>> xfft_pad = complex_pad_simple(xfft, fft_size)
    >>> np.testing.assert_array_almost_equal(x=expected_xfft_pad, y=xfft_pad,
    ... err_msg="The expected x is different than computed y")

    >>> # Check if it works for the case where padding should not be done.
    >>> # So expected result is the same as the xfft.
    >>> xfft = tensor([[[1.0, 2.0], [3.0, 4.0], [4.0, 5.0]]])
    >>> half_fft_size = xfft.shape[-2]
    >>> fft_size = (half_fft_size - 1) * 2
    >>> xfft_pad = complex_pad_simple(xfft, fft_size)
    >>> np.testing.assert_array_almost_equal(x=xfft, y=xfft_pad,
    ... err_msg="The expected x is different than computed y")

    Use the torch.nn.functional.pad.

    :param xfft: the fft-ed signal (containing complex numbers)
    :param fft_size: the initial size of the fft (before oneside-ing it).
    :return: the padded xfft signal.
    """
    half_fft = fft_size // 2 + 1
    current_length = xfft.shape[-2]
    if half_fft > current_length:
        pad_right = half_fft - current_length
        # We have to skip the last dimension that represents the complex number
        # so effectively we use the 2D padding for the 1D complex values.
        return F.pad(input=xfft, pad=(0, 0, 0, pad_right), mode="constant",
                     value=0)
    else:
        return xfft


def complex_pad2D(fft_input, half_fft_height, half_fft_width):
    """
    >>> # Typical use case.
    >>> xfft = tensor([[[1.0, 2.0], [3.0, 4.0], [4.0, 5.0]],
    ... [[2.0, 1.0], [-1.0, 2.0], [5.0, 1.0]]])
    >>> expected_xfft_pad = tensor([[[1.0, 2.0], [3.0, 4.0], [4.0, 5.0],
    ... [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]],
    ... [[2.0, 1.0], [-1.0, 2.0], [5.0, 1.0], [0., 0.], [0., 0.], [0., 0.]],
    ... [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0., 0.], [0., 0.], [0., 0.]]])
    >>> half_fft_width = xfft.shape[-2] + 3  # width
    >>> half_fft_height = xfft.shape[-3] + 1  # height
    >>> xfft_pad = complex_pad2D(fft_input=xfft, half_fft_height=half_fft_height,
    ... half_fft_width=half_fft_width)
    >>> np.testing.assert_array_almost_equal(x=expected_xfft_pad, y=xfft_pad,
    ... err_msg="The expected x is different than computed y")

    >>> # Only two dimensions (the -2 being the "true one" and the last one is
    >>> # for the complex numbers.
    >>> xfft = tensor([[[1.0, 0.0], [0.0, 4.0], [4.0, 5.0], [-1.0, 0.0]]])
    >>> expected_xfft_pad = tensor([[[1.0, 0.0], [0.0, 4.0], [4.0, 5.0],
    ... [-1.0, 0.0], [0.0, 0.0], [0.0, 0.0]], [[0.0, 0.0], [0.0, 0.0],
    ... [0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]])
    >>> half_fft_width = xfft.shape[-2] + 2
    >>> half_fft_height = xfft.shape[-3] + 1
    >>> xfft_pad = complex_pad2D(fft_input=xfft, half_fft_height=half_fft_height,
    ... half_fft_width=half_fft_width)
    >>> np.testing.assert_array_almost_equal(x=expected_xfft_pad, y=xfft_pad,
    ... err_msg="The expected x is different than computed y")

    >>> # Check if works for the case where padding should not be done.
    >>> # So expected result is the same as the xfft.
    >>> xfft = tensor([[[1.0, 2.0], [3.0, 4.0], [4.0, 5.0]]])
    >>> half_fft_width = xfft.shape[-2]
    >>> half_fft_height = xfft.shape[-3]
    >>> xfft_pad = complex_pad2D(fft_input=xfft, half_fft_height=half_fft_height,
    ... half_fft_width=half_fft_width)
    >>> np.testing.assert_array_almost_equal(x=xfft, y=xfft_pad,
    ... err_msg="The expected x is different than computed y")

    Pad xfft with zeros in the frequency domain to the size specified with
    fft_height and fft_width.

    :param xfft: the input signal in the frequency domain (represented by
    complex numbers).
    :param half_fft_height: the expected initial half fft height (the last but
    one dimension for real numbers and one further "into depth" dimension for
    complex numbers) used in the forward pass.
    :param half_fft_width: the expected initial half fft width (the last
    dimension for real numbers and the one more "into depth" dimension for
    complex numbers) used in the forward pass.
    :return: the padded xfft signal with zeros in the frequency domain.
    """
    # Omit the last dimension (-1) for complex numbers.
    current_height = fft_input.shape[-3]
    current_width = fft_input.shape[-2]
    if current_height < half_fft_height or current_width < half_fft_width:
        pad_bottom = half_fft_height - current_height
        pad_right = half_fft_width - current_width
        return F.pad(fft_input, (0, 0, 0, pad_right, 0, pad_bottom))
    return fft_input


def fast_jmul(input, filter):
    """
    Fast complex multiplication.

    :param input: fft-ed complex input.
    :param filter: fft-ed complex.

    input_re: real part of the input (a).
    input_im: imaginary part of the input (b).
    filter_re: real part of the filter (c).
    filter_im: imaginary part of the filter (d).

    :return: the result of the complex multiplication.

    >>> x = tensor([[5., 5.]])
    >>> y = tensor([[-1., 2.]])
    >>> xy = fast_jmul(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[-15., 5.]]))

    >>> # complex multiply for 2D (complex) tensors
    >>> x = tensor([[[[1., 2.], [5., 5.]], [[2., 1.], [3., 3.]]]])
    >>> y = tensor([[[[2., 3.], [-1., 2.]], [[0.0, 2.0], [2., 1.]]]])
    >>> xy = fast_jmul(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[[[-4., 7.], [-15., 5.0]],
    ... [[-2., 4.0], [3.0, 9.]]]]))

    >>> x = tensor([[ 6.,  0.], [0., -2.], [1., 0.], [ 1.,  1.],
    ... [1., 2.]])
    >>> y = tensor([[2.,  0.], [0., -6.], [0., 1.], [ 1.,  1.],
    ... [2., 3.]])
    >>> np.testing.assert_array_equal(fast_jmul(x, y),
    ... tensor([[12.,   0.], [-12., 0.], [0., 1.], [ 0.,   2.],
    ... [-4., 7.]]))
    >>> # x = torch.rfft(torch.tensor([1., 2., 3., 0.]), 1)
    >>> x = tensor([[ 6.,  0.], [-2., -2.], [ 2.,  0.]])
    >>> # y = torch.rfft(torch.tensor([5., 6., 7., 0.]), 1)
    >>> y = tensor([[18.,  0.], [-2., -6.], [ 6.,  0.]])
    >>> # torch.equal(tensor1, tensor2): True if two tensors
    >>> # have the same size and elements, False otherwise.
    >>> np.testing.assert_array_equal(fast_jmul(x, y),
    ... tensor([[108.,   0.], [ -8.,  16.], [ 12.,   0.]]))

    >>> x = tensor([[1., 2.]])
    >>> y = tensor([[2., 3.]])
    >>> xy = fast_jmul(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[-4., 7.]]))

    >>> x = tensor([[5., 5.]])
    >>> y = tensor([[-1., 2.]])
    >>> xy = fast_jmul(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[-15., 5.]]))

    >>> x = tensor([[[1., 2.]]])
    >>> y = tensor([[[2., 3.]]])
    >>> xy = fast_jmul(x, y)
    >>> np.testing.assert_array_equal(xy, tensor([[[-4., 7.]]]))

    >>> x = tensor([[[1., 2.], [3., 1.]]])
    >>> y = tensor([[[2., 3.], [1., 2.]]])
    >>> xy = fast_jmul(x, y)
    >>> np.testing.assert_array_equal(xy,
    ... tensor([[[-4., 7.], [1., 7.]]]))

    >>> x = tensor([[[1., 2.], [3., 1.]], [[ 6.,  0.], [-2., -2.]]])
    >>> y = tensor([[[2., 3.], [1., 2.]], [[18.,  0.], [-2., -6.]]])
    >>> xy = fast_jmul(x, y)
    >>> np.testing.assert_array_equal(xy,
    ... tensor([[[-4., 7.], [1., 7.]], [[108.,   0.], [ -8.,  16.]]]))
    >>> del x
    >>> del y
    >>> del xy
    """
    a = input[..., :1]
    b = input[..., 1:]
    c = filter[..., :1]
    d = filter[..., 1:]

    ac = torch.mul(a, c)
    bd = torch.mul(b, d)

    a_bc_d = torch.mul(torch.add(a, b), torch.add(c, d))
    out_re = ac - bd
    out_im = a_bc_d - ac - bd

    out = torch.cat((out_re, out_im), -1)

    return out


def retain_low_coef(xfft, preserve_energy=None, index_back=None):
    """
    Retain the low coefficients to either to reach the required
    preserve_energy or after removing index_back coefficients. Only one of them
    should be chosen. The coefficients with the highest frequencies are
    discarded (they usually represent noise for naturla signals and images).

    :param xfft: the input signal (4 dimensions: batch size, channel, signal,
    complex numbers).
    :param preserve_energy: the percentage of energy to be preserved
    :param index_back: the number of zeroed out coefficients (starting from the
    smallest one).
    :return: the zeroed-out small coefficients

    >>> # Simple index_back.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]]]])
    >>> result = retain_low_coef(xfft, index_back=1)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Simple preserved energy.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]]]])
    >>> result = retain_low_coef(xfft, preserve_energy=90)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Simple preserved energy.
    >>> xfft = torch.tensor([[[[0.1, 0.1], [30., 40.], [1.1, 2.1], [0.1, -0.8],
    ... [0.0, -1.0]]]])
    >>> result = retain_low_coef(xfft, preserve_energy=5)
    >>> expected = torch.tensor([[[[0.1, 0.1], [30., 40.], [0.0, 0.0],
    ... [0.0, 0.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Simple index back.
    >>> xfft = torch.tensor([[[[1.1, 2.1], [30., 40.], [0.1, 0.1], [0.1, -0.8],
    ... [0.0, -1.0]]]])
    >>> result = retain_low_coef(xfft, index_back=3)
    >>> expected = torch.tensor([[[[1.1, 2.1], [30., 40.], [0.0, 0.0],
    ... [0.0, 0.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Check 2 channels for preserved energy.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]],
    ... [[0.0, 0.1], [2.0, -6.0], [0.01, 0.002]]]])
    >>> result = retain_low_coef(xfft, preserve_energy=90)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]],
    ... [[0.0, 0.1], [2.0, -6.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Check 2 data points for preserved energy.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]]],
    ... [[[0.0, 0.1], [2.0, -6.0], [0.01, 0.002]]]])
    >>> result = retain_low_coef(xfft, preserve_energy=90)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]]],
    ... [[[0.0, 0.1], [2.0, -6.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Check 2 channels for index back.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]],
    ... [[0.0, 0.1], [2.0, -6.0], [0.01, 0.002]]]])
    >>> result = retain_low_coef(xfft, preserve_energy=90)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]],
    ... [[0.0, 0.1], [2.0, -6.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Check 2 data points for index back.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]]],
    ... [[[0.0, 0.1], [2.0, -6.0], [0.01, 0.002]]]])
    >>> result = retain_low_coef(xfft, index_back=1)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]]],
    ... [[[0.0, 0.1], [2.0, -6.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())
    >>> del xfft
    >>> del expected
    """
    INPUT_ERROR = "Specify only one of: index_back, preserve_energy"
    if (index_back is not None and index_back > 0) and (
            preserve_energy is not None and preserve_energy < 100):
        raise TypeError(INPUT_ERROR)
    if xfft is None or len(xfft) == 0:
        return xfft
    if (preserve_energy is not None and preserve_energy < 100) or (
            index_back is not None and index_back > 0):
        out = torch.zeros_like(xfft, device=xfft.device)
        for data_point_index, data_point_value in enumerate(xfft):
            for channel_index, channel_value in enumerate(data_point_value):
                full_energy, squared = get_full_energy(channel_value)
                current_energy = 0.0
                preserved_indexes = len(squared)
                if index_back is not None:
                    preserved_indexes = len(squared) - index_back
                preserved_energy = full_energy
                if preserve_energy is not None:
                    preserved_energy = full_energy * preserve_energy / 100
                index = 0
                while current_energy < preserved_energy and (
                        index < preserved_indexes):
                    energy = squared[index]
                    # np.testing.assert_almost_equal(actual=energy,
                    #                                desired=squared[coeff_index])
                    current_energy += energy
                    out[data_point_index, channel_index, index, :] = \
                        xfft[data_point_index, channel_index, index, :]
                    index += 1
        return out
    return xfft


def retain_big_coef(xfft, preserve_energy=None, index_back=None):
    """
    Retain the largest coefficients to either to reach the required
    preserve_energy or after removing index_back coefficients. Only one of them
    should be chosen.

    :param xfft: the input signal (4 dimensions: batch size, channel, signal,
    complex numbers).
    :param preserve_energy: the percentage of energy to be preserved
    :param index_back: the number of zeroed out coefficients (starting from the
    smallest one).
    :return: the zeroed-out small coefficients

    >>> # Simple index_back.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]]]])
    >>> result = retain_big_coef(xfft, index_back=1)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Simple preserved energy.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]]]])
    >>> result = retain_big_coef(xfft, preserve_energy=90)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Simple preserved energy.
    >>> xfft = torch.tensor([[[[1.1, 2.1], [30., 40.], [0.1, 0.1], [0.1, -0.8],
    ... [0.0, -1.0]]]])
    >>> result = retain_big_coef(xfft, preserve_energy=5)
    >>> expected = torch.tensor([[[[0.0, 0.0], [30., 40.], [0.0, 0.0],
    ... [0.0, 0.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Simple index back.
    >>> xfft = torch.tensor([[[[0.1, 0.1], [30., 40.], [1.1, 2.1], [0.1, -0.8],
    ... [0.0, -1.0]]]])
    >>> result = retain_big_coef(xfft, index_back=3)
    >>> expected = torch.tensor([[[[0.0, 0.0], [30., 40.], [1.1, 2.1],
    ... [0.0, 0.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Check 2 channels for preserved energy.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]],
    ... [[0.0, 0.1], [2.0, -6.0], [0.01, 0.002]]]])
    >>> result = retain_big_coef(xfft, preserve_energy=90)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]],
    ... [[0.0, 0.0], [2.0, -6.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Check 2 data points for preserved energy.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]]],
    ... [[[0.0, 0.1], [2.0, -6.0], [0.01, 0.002]]]])
    >>> result = retain_big_coef(xfft, preserve_energy=90)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]]],
    ... [[[0.0, 0.0], [2.0, -6.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Check 2 channels for index back.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]],
    ... [[0.0, 0.1], [2.0, -6.0], [0.01, 0.002]]]])
    >>> result = retain_big_coef(xfft, preserve_energy=90)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]],
    ... [[0.0, 0.0], [2.0, -6.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Check 2 data points for index back.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]]],
    ... [[[0.01, 0.002], [2.0, -6.0], [0.0, 0.1]]]])
    >>> result = retain_big_coef(xfft, index_back=1)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]]],
    ... [[[0.0, 0.0], [2.0, -6.0], [0.0, 0.1]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())
    >>> del xfft
    >>> del expected
    """
    INPUT_ERROR = "Specify only one of: index_back, preserve_energy"
    if (index_back is not None and index_back > 0) and (
            preserve_energy is not None and preserve_energy < 100):
        raise TypeError(INPUT_ERROR)
    if xfft is None or len(xfft) == 0:
        return xfft
    if (preserve_energy is not None and preserve_energy < 100) or (
            index_back is not None and index_back > 0):
        out = torch.zeros_like(xfft, device=xfft.device)
        for data_point_index, data_point_value in enumerate(xfft):
            for channel_index, channel_value in enumerate(data_point_value):
                full_energy, squared = get_full_energy(channel_value)
                current_energy = 0.0
                added_indexes = 0
                preserved_indexes = len(squared)
                if index_back is not None:
                    preserved_indexes = len(squared) - index_back
                preserved_energy = full_energy
                if preserve_energy is not None:
                    preserved_energy = full_energy * preserve_energy / 100
                # Creates the priority queue with the pair: coefficient
                # absolute value and the position (index) in the signal
                # (array).
                heap = []
                # Index and value of a coefficient.
                for square_index, square_value in enumerate(squared):
                    # We want to get the largest coefficients.
                    heappush(heap, (-square_value, square_index))
                while current_energy < preserved_energy and (
                        added_indexes < preserved_indexes):
                    neg_energy, coeff_index = heappop(heap)
                    energy = (-neg_energy.item())
                    # np.testing.assert_almost_equal(actual=energy,
                    #                                desired=squared[coeff_index])
                    current_energy += (-neg_energy)
                    added_indexes += 1
                    out[data_point_index, channel_index, coeff_index, :] = \
                        xfft[data_point_index, channel_index, coeff_index, :]
        return out
    return xfft


def retain_big_coef_bulk(xfft, preserve_energy=None, index_back=None):
    """
    Retain the largest coefficients to either to reach the required
    preserve_energy or after removing index_back coefficients. Only one of them
    should be chosen.

    :param xfft: the input signal (4 dimensions: batch size, channel, signal,
    complex numbers).
    :param preserve_energy: the percentage of energy to be preserved
    :param index_back: the number of zeroed out coefficients (starting from the
    smallest one).
    :return: the zeroed-out small coefficients

    >>> # Simple index_back.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]]]])
    >>> result = retain_big_coef_bulk(xfft, index_back=1)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Simple preserved energy.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]]]])
    >>> result = retain_big_coef_bulk(xfft, preserve_energy=90)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Simple preserved energy.
    >>> xfft = torch.tensor([[[[1.1, 2.1], [30., 40.], [0.1, 0.1], [0.1, -0.8],
    ... [0.0, -1.0]]]])
    >>> result = retain_big_coef_bulk(xfft, preserve_energy=5)
    >>> expected = torch.tensor([[[[0.0, 0.0], [30., 40.], [0.0, 0.0],
    ... [0.0, 0.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Simple index back.
    >>> xfft = torch.tensor([[[[0.1, 0.1], [30., 40.], [1.1, 2.1], [0.1, -0.8],
    ... [0.0, -1.0]]]])
    >>> result = retain_big_coef_bulk(xfft, index_back=3)
    >>> expected = torch.tensor([[[[0.0, 0.0], [30., 40.], [1.1, 2.1],
    ... [0.0, 0.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Check 2 channels for preserved energy.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]],
    ... [[0.0, 0.1], [2.0, -6.0], [0.01, 0.002]]]])
    >>> result = retain_big_coef_bulk(xfft, preserve_energy=90)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]],
    ... [[0.0, 0.0], [2.0, -6.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Check 2 data points for preserved energy.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]]],
    ... [[[0.0, 0.1], [2.0, -6.0], [0.01, 0.002]]]])
    >>> result = retain_big_coef_bulk(xfft, preserve_energy=90)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]]],
    ... [[[0.0, 0.0], [2.0, -6.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Check 2 channels for index back.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]],
    ... [[0.0, 0.1], [2.0, -6.0], [0.01, 0.002]]]])
    >>> result = retain_big_coef_bulk(xfft, preserve_energy=90)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]],
    ... [[0.0, 0.0], [2.0, -6.0], [0.0, 0.0]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())

    >>> # Check 2 data points for index back.
    >>> xfft = torch.tensor([[[[1., 2.], [3., 4.], [0.1, 0.1]]],
    ... [[[0.01, 0.002], [2.0, -6.0], [0.0, 0.1]]]])
    >>> result = retain_big_coef_bulk(xfft, index_back=1)
    >>> expected = torch.tensor([[[[1., 2.], [3., 4.], [0.0, 0.0]]],
    ... [[[0.0, 0.0], [2.0, -6.0], [0.0, 0.1]]]])
    >>> np.testing.assert_equal(actual=result.numpy(), desired=expected.numpy())
    >>> del xfft
    >>> del expected
    """
    INPUT_ERROR = "Specify only one of: index_back, preserve_energy"
    if (index_back is not None and index_back > 0) and (
            preserve_energy is not None and preserve_energy < 100):
        raise TypeError(INPUT_ERROR)
    if xfft is None or len(xfft) == 0:
        return xfft
    if (preserve_energy is not None and preserve_energy < 100) or (
            index_back is not None and index_back > 0):
        out = torch.zeros_like(xfft, device=xfft.device)
        full_energy_bulk, squared_bulk = get_full_energy_bulk(xfft)
        # plot_signal_freq(squared_bulk[0, 0].numpy())
        squared_bulk, indices_bulk = torch.sort(squared_bulk, descending=True)
        N, C, _, _ = xfft.size()
        for data_point_index in range(N):
            for channel_index in range(C):
                full_energy = full_energy_bulk[data_point_index, channel_index]
                squared = squared_bulk[data_point_index, channel_index]
                indices = indices_bulk[data_point_index, channel_index]
                current_energy = 0.0
                added_index = 0
                # Number of coefficients in the squared array (the amplitudes of
                # the coefficients).
                preserved_indexes = len(squared)
                if index_back is not None:
                    preserved_indexes -= index_back
                preserved_energy = full_energy
                if preserve_energy is not None:
                    preserved_energy = full_energy * preserve_energy / 100
                while current_energy < preserved_energy and (
                        added_index < preserved_indexes):
                    energy = squared[added_index]
                    coeff_index = indices[added_index]
                    current_energy += energy
                    added_index += 1
                    out[data_point_index, channel_index, coeff_index, :] = \
                        xfft[data_point_index, channel_index, coeff_index, :]
        return out
    return xfft


def cuda_mem_show(is_debug=True, info="", omit_objs=[]):
    if torch.cuda.is_available() and is_debug is True:
        cuda_mem_empty(is_debug=is_debug)
        only_cuda = True
        tensor_size = get_tensors_elem_size(only_cuda=only_cuda,
                                            omit_objs=omit_objs)
        tensor_count = get_tensors_elem_count(only_cuda=only_cuda)
        with open(mem_log_file, "a") as f:
            f.write(
                f"info,{info},memory allocated,{torch.cuda.memory_allocated()},max memory allocated,{torch.cuda.max_memory_allocated()},memory cached,{torch.cuda.memory_cached()},max memory cached,{torch.cuda.max_memory_cached()},total nr (count) of cuda tensor elements,{tensor_count},total size of cuda tensors,{tensor_size}\n")


def cuda_mem_empty(is_debug=True):
    if torch.cuda.is_available() and is_debug is True:
        # print("cuda empty cache")
        torch.cuda.empty_cache()


def get_all_tensor_names():
    """
    >>> clean_gc_return = map((lambda obj: del_object(obj)), gc.get_objects())
    >>> t1 = tensor([1])
    >>> a3 = tensor([1, 2, 3])
    >>> # print(get_all_tensor_names())
    >>> names = get_all_tensor_names()
    >>> # print("tensor names: ", names)
    >>> # print("lenght of tensor names: ", len(names))
    >>> assert len(names) == 2
    >>> assert names == {'a3', 't1'}
    >>> del t1
    >>> del a3
    """
    tensor_names = set()
    try:
        for obj in gc.get_objects():
            obj_names = re.findall(r"'(\w+)': tensor\(", str(obj))
            tensor_names.update(obj_names)
    except:
        pass
    return tensor_names


def del_object(obj):
    del obj


def get_tensors(only_cuda=False, is_debug=False, omit_objs=[]):
    """
    https://discuss.pytorch.org/t/how-to-debug-causes-of-gpu-memory-leaks/6741/3?u=adam_dziedzic

    :return: list of active PyTorch tensors
    >>> import torch
    >>> from torch import tensor
    >>> clean_gc_return = map((lambda obj: del_object(obj)), gc.get_objects())
    >>> device = "cuda" if torch.cuda.is_available() else "cpu"
    >>> device = torch.device(device)
    >>> only_cuda = True if torch.cuda.is_available() else False
    >>> t1 = tensor([1], device=device)
    >>> a3 = tensor([[1, 2], [3, 4]], device=device)
    >>> # print(get_all_tensor_names())
    >>> tensors = [tensor_obj for tensor_obj in get_tensors(only_cuda=only_cuda)]
    >>> # print(tensors)
    >>> # We doubled each t1, a3 tensors because of the tensors collection.
    >>> expected_tensor_length = 2
    >>> assert len(tensors) == expected_tensor_length, f"Expected length of tensors {expected_tensor_length}, but got {len(tensors)}, the tensors: {tensors}"
    >>> exp_size = (2,2)
    >>> act_size = tensors[1].size()
    >>> assert exp_size == act_size, f"Expected size {exp_size} but got: {act_size}"
    >>> del t1
    >>> del a3
    >>> clean_gc_return = map((lambda obj: del_object(obj)), tensors)
    """
    add_all_tensors = False if only_cuda is True else True
    # To avoid counting the same tensor twice, create a dictionary of tensors,
    # each one identified by its id (the in memory address).
    tensors = {}
    # omit_obj_ids = [id(obj) for obj in omit_objs]

    def add_tensor(obj):
        tensor = None
        if torch.is_tensor(obj):
            tensor = obj
        elif hasattr(obj, 'data') and torch.is_tensor(obj.data):
            tensor = obj.data
        else:
            return

        if (only_cuda and tensor.is_cuda) or add_all_tensors:
            tensors[id(tensor)] = tensor

    for obj in gc.get_objects():
        try:
            # Add the obj if it is a tensor.
            add_tensor(obj)
            # Some tensors are "saved & hidden" for the backward pass.
            if hasattr(obj, 'saved_tensors') and (id(obj) not in omit_objs):
                for tensor_obj in obj.saved_tensors:
                    add_tensor(tensor_obj)
        except Exception as ex:
            pass
            # print("Exception: ", ex)
            # logger.debug(f"Exception: {str(ex)}")
    return tensors.values()  # return a list of tensors


def get_tensors_elem_count(only_cuda=True):
    """
    Get total number of elements in tensors.

    :return: the total number of elements (floats, doubles, etc.) in tensors.
    """
    tensors = get_tensors(only_cuda=only_cuda)
    total_elem = 0
    for tensor_obj in tensors:
        # sizes = [size for size in tensor_obj.size()]
        # if len(sizes) == 1:
        #     total_elem += sizes[0]
        # elif len(sizes) > 1:
        #     total_elem += reduce((lambda x, y: x * y), sizes)
        total_elem += tensor_obj.numel()
    return total_elem


def get_elem_size(tensor_obj):
    """

    :param tensor_obj: a tensor
    :return: the size in bytes of a single element in the tensor based on its
    type

    >>> t1 = tensor([1,2,3], dtype=torch.int32)
    >>> size = get_elem_size(t1)
    >>> assert size == 4
    >>> del t1
    >>> t2 = tensor([1.,2.,3.], dtype=torch.float)
    >>> size = get_elem_size(t2)
    >>> assert size == 4
    >>> del t2
    >>> t3 = tensor([1.,2.,3.], dtype=torch.float16)
    >>> size = get_elem_size(t3)
    >>> assert size == 2
    >>> del t3
    >>> t4 = tensor([1.,2.,3.], dtype=torch.double)
    >>> size = get_elem_size(t4)
    >>> assert size == 8
    >>> del t4
    """
    obj_type = tensor_obj.dtype

    if (obj_type is torch.float64) or (obj_type is torch.double) or (
            obj_type is torch.int64) or (obj_type is torch.long):
        return 8
    elif (obj_type is torch.float32) or (obj_type is torch.float) or (
            obj_type is torch.int32) or (obj_type is torch.int):
        return 4
    elif (obj_type is torch.float16) or (obj_type is torch.half) or (
            obj_type is torch.int16) or (obj_type is torch.short):
        return 2
    elif (obj_type is torch.int8) or (obj_type is torch.uint8):
        return 1
    else:
        raise AttributeError(f"Unknown torch type: {obj_type}")


def get_tensors_elem_size_count(only_cuda=True):
    """
    Get total size of elements in tensors.

    :return: the total size in bytes and total count (number) of elements
    (floats, doubles, etc.) in tensors.

    >>> clean_gc_return = map((lambda obj: del_object(obj)), gc.get_objects())
    >>> device = "cuda" if torch.cuda.is_available() else "cpu"
    >>> device = torch.device(device)
    >>> only_cuda = True if torch.cuda.is_available() else False
    >>> t1 = tensor([1, 2, 3, 4], dtype=torch.int32, device=device)
    >>> t4 = tensor([1., 2., 3.], dtype=torch.double, device=device)
    >>> only_cuda = True if torch.cuda.is_available() else False
    >>> size, count = get_tensors_elem_size_count(only_cuda=only_cuda)
    >>> # print("tensors: ", get_tensors())
    >>> assert size == 40, f"Expected size 40, but got {size}"
    >>> assert count == 7, f"Expected count 7, but got {count}"
    """
    tensors = [tensor_obj for tensor_obj in get_tensors(only_cuda=only_cuda)]
    total_size = 0
    total_count = 0
    for tensor_obj in tensors:
        # sizes = [size for size in tensor_obj.size()]
        # if len(sizes) == 1:
        #     total_count += sizes[0]
        # elif len(sizes) > 1:
        #     total_count += reduce((lambda x, y: x * y), sizes)
        count = tensor_obj.numel()
        total_size += count * get_elem_size(tensor_obj)
        total_count += count
    return total_size, total_count


def get_tensors_elem_size(only_cuda=True, omit_objs=[]):
    """
    Get total size of elements in tensors.

    :param only_cuda: count only tensors on gpu
    :param omit_obs: omit the objects (for example, we
    don't want to count object twice, it saved_tensors in the context in the
    backward pass and the retrieved objects (tensors) from the context.

    :return: the total size in bytes and total count (number) of elements
    (floats, doubles, etc.) in tensors.

    >>> clean_gc_return = map((lambda obj: del_object(obj)), gc.get_objects())
    >>> device = "cuda" if torch.cuda.is_available() else "cpu"
    >>> device = torch.device(device)
    >>> only_cuda = True if torch.cuda.is_available() else False
    >>> t1 = tensor([1, 2, 3, 4], dtype=torch.int32, device=device)
    >>> t4 = tensor([1., 2., 3.], dtype=torch.double, device=device)
    >>> only_cuda = True if torch.cuda.is_available() else False
    >>> size = get_tensors_elem_size(only_cuda=only_cuda)
    >>> assert size == 40
    """
    total_size = 0
    for tensor_obj in get_tensors(only_cuda=only_cuda, omit_objs=omit_objs):
        total_size += tensor_obj.numel() * get_elem_size(tensor_obj)
    return total_size


if __name__ == "__main__":
    import sys
    import doctest

    clean_gc_return = map((lambda obj: del_object(obj)), gc.get_objects())
    if torch.cuda.is_available():
        device = torch.device("cuda")
        t1 = tensor([1], device=device)
        a3 = tensor([[1, -2], [3, -4]], device=device)
        tensor_obj = None

        tensors = get_tensors(only_cuda=True, is_debug=True)
        for tensor_obj in tensors:
            print("tensor: ", tensor_obj)
        del tensor_obj
        tensors = get_tensors(only_cuda=True)
        for tensor_obj in tensors:
            print("tensor_obj: ", tensor_obj)
        del tensor_obj
        total_elem_nr = get_tensors_elem_count()
        print("total number of elements (items) in all tensors: ",
              total_elem_nr)
        expected = 5
        assert total_elem_nr == 5, f"Expected {expected} but got: {total_elem_nr}"
        del t1
        del a3
        del tensors

    # you can run it from the console: python pytorch_util.py -v
    sys.exit(doctest.testmod()[0])
