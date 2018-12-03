#include <ATen/ATen.h>

#include <cuda.h>
#include <cuda_runtime.h>
#include <cstdio>
#include <cmath>

namespace {

/**
The high pole in the tent for the FFT based convolution is the element-wise
complex multiplication between each input map and each filter. It is not the
cost of the FFT operation, which for an input map of size NxCxHxW is N * C *
H * log H * W * log W and for a filter bank of size FxCxHxW is
F * C * H * log H * W * log W * I. The cost of the inverse FFT is;
N*F*H*logH*W*logW*I. The total cost of FFT is: H*logH*W*logW*(N*C+F*C+N*F*I).
The cost of the convolution in the frequency
domain is: N * F * C * H * W * 3 (the minimum number of real multiplications
in complex multiplication of two numbers), which is greater than the cost of FFT since:
N * F * C * I >> logH*logW*(N*C+F*C+N*F*I). We can estimate it by omitting I=2.
and assuming X can be substituted for N, F, and C, H, W. X^3 >> 4X^2log^2X.
We can consider the first filter from the ResNet-18 for CIFAR10 with batch of
size 128. The cost of FFT operations is: 5*5*(128*3+64*3+128*64*2) = 424000.
The cost of the convolution in the frequency domain is:
128 * 64 * 3 * 32 * 32 * 3 = 75497472. The cost of convolution is about more
than two orders of magnitude greater.

Our method aims at saving memory and utilizing as many GPU threads as
possible. We fuse the elementwise complex multiplication with the summation
along a given channel in a thread execution path to limit the memory size (from
N * F * C * H * W * I to the actual size of the output: N * F * H * W * I),
and avoid any additional synchronization by focusing on computation
of a single output cell (of coordinates: [n,f,h,w] in an output map.

The total number of GPU thread blocks is N * F * max threads per block: number
of input maps (e.g. images) in the batch and number of filers in the filter
bank.
Each block of threads is used to compute a single output plane of size
(H x W x I), which correspond to the f-th channel plane in the n-th output map.
It is obtained after a point-wise complex multiplication between an input map n
and a filter f both of size H x W x I.
Each thread in a block of threads drills through each channel in an input map
on the level of a given (H,W) coordinate.
For image n, we set its starting index n_idx from n*C*H*W*I and the last
coordinate for a given plane is at (n_idx+H*W*I) = n_idx + channel_size (a
single channel size).
We define the number of threads in the block as a raw_stride.
Once a thread finishes summing values for all the channels C in the (H,W)
coordinate, it moves (raw_stride*(*W*I) = stride) positions to the next (H,W)
coordinate to be computed or finishes its execution.

We use min(max_threads_in_block, H*W) threads per block.

*/
template <typename scalar_t>
__global__ void complex_mul_cuda_kernel(
    const scalar_t* __restrict__ x,
    const scalar_t* __restrict__ y,
    scalar_t* __restrict__ out,
    const int N, const int F, const int C, const int H, const int W) {

    const int I = 2; // the last dimension for the complex number
    const int plane_size = H * W;
    const int channel_size = plane_size * I;
    const int image_size = C * channel_size;  // size of the image from the batch

    const int n = blockIdx.x; // current index of an image/input map in the batch
    const int f = blockIdx.y; // current index of a filter from the filter bank
    const int start = threadIdx.x; // current XY cell to be computed (element wise multiplication between corresponding cells in the image and filter, then summed up
    // number of threads per block
    const int raw_stride = blockDim.x;  // stride for the H*W map is equal to the number of threads declared in a block
    const int stride = raw_stride * I; // we need HxW threads per plane

    const int n_idx = n * image_size;  // start index in the batch for this input map
    const int f_idx = f * image_size;  // start index in the bank for this filter

    // find index for the output
    const int no_idx = n * (F * channel_size); // output index for the batch data point
    const int fo_idx = f * channel_size;       // output index for the filter/channel

    const int start_idx = start*I;

    // index in the input map
    int N_idx = n_idx + start_idx; // index across the first channel plane (in the input map n).
    const int last_N_idx = n_idx + H * W * I;  // last index for the starting position to compute the sum through each channel for this pixel

    // index in the filter
    int F_idx = f_idx + start_idx; // index across the first channel plane (in the filter f).

    // index in the output
    int O_idx = no_idx + fo_idx + start_idx;

    while (N_idx < last_N_idx)  {
        int cN_idx = N_idx;  // current input n index across the channels
        int cF_idx = F_idx;  // current filter f index across the channels

        scalar_t out_re = 0.0f;
        scalar_t out_im = 0.0f;

        for (int c = 0; c < C; ++c) {
//            printf("n:%d,N_idx:%d,f:%d,threadIdx.x:%d,cN_idx:%d,cF_idx:%d,last_N_idx:%d\n", n, N_idx, f, threadIdx.x, cN_idx, cF_idx, last_N_idx);
//            if (N_idx > N*C*H*W*I || F_idx > F*C*H*W*I)
//                printf("error out of bound\n");
            scalar_t x_re = x[cN_idx];
            scalar_t x_im = x[cN_idx + 1];
            scalar_t y_re = y[cF_idx];
            scalar_t y_im = y[cF_idx + 1];
            single_mul(x_re, x_im, y_re, y_im, &out_re, &out_im);
            // x[cN_idx] = x[cN_idx + 1];
            cN_idx += channel_size;
            cF_idx += channel_size;
        }
//        if (out[O_idx] > 1 || out[O_idx + 1] > 1) {
//            printf("n:%d,N_idx:%d,f:%d,threadIdx.x:%d,cN_idx:%d,cF_idx:%d,last_N_idx:%d,O_idx:%d,re:%f,im:%f. Error, the position was already computed.\n", n, N_idx, f, threadIdx.x, cN_idx, cF_idx, last_N_idx, O_idx, out[O_idx], out[O_idx+1]);
//        } else {
//            printf("n:%d,N_idx:%d,f:%d,threadIdx.x:%d,cN_idx:%d,cF_idx:%d,last_N_idx:%d,O_idx:%d,re:%f,im:%f. Correct.\n", n, N_idx, f, threadIdx.x, cN_idx, cF_idx, last_N_idx, O_idx, out[O_idx], out[O_idx+1]);
//        }
        out[O_idx] = out_re;
        out[O_idx + 1] = out_im;

        N_idx += stride;
        F_idx += stride;
        O_idx += stride;
    }
}

template <typename scalar_t>
__device__ __forceinline__ void single_mul(
    scalar_t x_re,
    scalar_t x_im,
    scalar_t y_re,
    scalar_t y_im,
    scalar_t* out_re,
    scalar_t* out_im) {

    scalar_t uavc = x_re * (y_re + y_im);
    *out_re += uavc - (x_re + x_im) * y_im;
    *out_im += (x_im - x_re) * y_re + uavc;
}

template <typename scalar_t>
__device__ __forceinline__ void single_add(
    scalar_t x_re,
    scalar_t x_im,
    scalar_t y_re,
    scalar_t y_im,
    scalar_t* out_re,
    scalar_t* out_im) {

    *out_re += x_re + y_re;
    *out_im += x_im + y_im;
}

} // namespace

void complex_mul_stride_no_permute_cuda(
    at::Tensor x,
    at::Tensor y,
    at::Tensor out,
    int threads = 1024) {

    const auto N = x.size(0);  // batch_size
    const auto F = y.size(0);  // filter_bank_size
    const auto C = x.size(1);  // number of channels
    const auto H = x.size(2);  // height of the matrix
    const auto W = x.size(3);  // width of the matrix

    const auto x_blocks = N;
    const auto y_blocks = F;
    const dim3 blocks(x_blocks, y_blocks);

    AT_DISPATCH_FLOATING_TYPES(x.type(), "complex_mul_cuda",
    ([&] {
        complex_mul_cuda_kernel<scalar_t><<<blocks, threads>>>(
        x.data<scalar_t>(), y.data<scalar_t>(), out.data<scalar_t>(),
        N, F, C, H, W);
    }));
}

//template <typename scalar_t>
//void complex_mul_stride_no_permute_cuda_pure(
//    at::Tensor x,
//    at::Tensor y,
//    at::Tensor out,
//    int threads = 1024) {
//
//    const auto N = x.size(0);  // batch_size
//    const auto F = y.size(0);  // filter_bank_size
//    const auto C = x.size(1);  // number of channels
//    const auto H = x.size(2);  // height of the matrix
//    const auto W = x.size(3);  // width of the matrix
//
//    const auto x_blocks = N;
//    const auto y_blocks = F;
//    const dim3 blocks(x_blocks, y_blocks);
//
//    // Run kernel on the GPU
//    complex_mul_cuda_kernel<scalar_t><<<blocks, 1024>>>(
//        x.data<scalar_t>(), y.data<scalar_t>(), out.data<scalar_t>(),
//        N, F, C, H, W);
//}

/**
Uncomment the pytorch related stuff.

Compile:
ady@skr-compute1:/tmp/pycharm_project_154/cnns/nnlib/pytorch_cuda/complex_mul_cuda$ nvcc complex_mul_kernel_stride_no_permute.cu -o complex_mul_profile.out
ady@skr-compute1:/tmp/pycharm_project_154/cnns/nnlib/pytorch_cuda/complex_mul_cuda$ nvprof ./complex_mul_profile.out

nvidia

/usr/local/cuda/bin/nvcc -I/local/ady/anaconda3/lib/python3.6/site-packages/torch/lib/include -I/local/ady/anaconda3/lib/python3.6/site-packages/torch/lib/include/torch/csrc/api/include -I/local/ady/anaconda3/lib/python3.6/site-packages/torch/lib/include/TH -I/local/ady/anaconda3/lib/python3.6/site-packages/torch/lib/include/THC -I/usr/local/cuda/include -I/local/ady/anaconda3/include/python3.6m -c complex_mul_kernel.cu -o complex_mul_kernel_stride_no_permute.out -std=c++11
nvcc -I/local/ady/anaconda3/lib/python3.6/site-packages/torch/lib/include -I/local/ady/anaconda3/lib/python3.6/site-packages/torch/lib/include/torch/csrc/api/include -I/local/ady/anaconda3/lib/python3.6/site-packages/torch/lib/include/TH -I/local/ady/anaconda3/lib/python3.6/site-packages/torch/lib/include/THC -I/usr/local/cuda/include -I/local/ady/anaconda3/include/python3.6m complex_mul_kernel_stride_no_permute.cu -o complex_mul_kernel_stride_no_permute.out -std=c++11
Segmentation fault
*/
int main(void)
{
    int N = 32;
    int F = 1;
    int C = 1;
    int H = 8;
    int W = 8;
    int size_input = N * C * H * W * 2;
    int size_filter = F * C * H * W * 2;
    int size_output = N * F * H * W * 2;
    int cuda_block_threads = 32;

    // auto dims = {128, 32, 16, 8, 2};
    //    at::Tensor x = at::randn({128, 32, 16, 8, 2});
    //    at::Tensor y = at::randn({128, 32, 16, 8, 2});
    //    at::Tensor out = at::zeros({128, 32, 16, 8, 2});
    float *x, *y, * out;

    // Allocate unified memory - accessible from cpu or gpu
    cudaMallocManaged(&x, size_input*sizeof(float));
    cudaMallocManaged(&y, size_filter*sizeof(float));
    cudaMallocManaged(&out, size_output*sizeof(float));

    for (int i=0; i < size_input-1; i+=2) {
        x[i] = 8;
        x[i+1] = -1;
        y[i] = 1;
        y[i+1] = 2;
        out[i] = 0.0f;
        out[i+1] = 0.0f;
    }

    const dim3 blocks(N, F);

    for(int i=0; i<32; ++i)
        complex_mul_cuda_kernel<float><<<blocks, cuda_block_threads>>>(
            x, y, out, N, F, C, H, W);

    cudaFree(x);
    cudaFree(y);
    cudaFree(out);

    printf("finished computation\n");

    return 0;
}