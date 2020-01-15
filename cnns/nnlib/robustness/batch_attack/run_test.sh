timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'perturb' --noise_epsilons 0.01 --net_mode '0-0' --attack_iters 300 --batch_size 3584 --limit_batch_number 0 --c 0.0 0.0001 0.0005 0.001 0.005 0.01 0.02 0.03 0.04 0.05 0.07 0.1 0.2 0.3 0.4 0.5 1.0 2.0 10.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
skr-compute1

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'perturb' --noise_epsilons 100.0 10.0 1.0 0.1 0.01 0.001 --net_mode '0-0' --attack_iters 1 --batch_size 3584 --limit_batch_number 1 --c 0.01 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
skr-compute1

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=1 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'perturb' --noise_epsilons 0.04 --net_mode '0-0' --attack_iters 300 --batch_size 2048 --limit_batch_number 0 --c 100.0 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
nips 1

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'perturb' --noise_epsilons 0.035 --net_mode '0-0' --attack_iters 300 --batch_size 2048 --limit_batch_number 0 --c 100.0 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
nips 0


timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'perturb' --noise_epsilons 0.045 --net_mode '0-0' --attack_iters 300 --batch_size 2048 --limit_batch_number 0 --c 100.0 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
wifi 0

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=1 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'perturb' --noise_epsilons 0.032 --net_mode '0-0' --attack_iters 300 --batch_size 2048 --limit_batch_number 0 --c 100.0 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
wifi 1

cc@wifi:~/code/bandlimited-cnns/cnns/nnlib/robustness/batch_attack$ nvidia-smi
Sun Jan 12 20:35:25 2020
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 418.40.04    Driver Version: 418.40.04    CUDA Version: 10.1     |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  Tesla P100-PCIE...  Off  | 00000000:03:00.0 Off |                    0 |
| N/A   32C    P0    37W / 250W |  14869MiB / 16280MiB |     83%      Default |
+-------------------------------+----------------------+----------------------+
|   1  Tesla P100-PCIE...  Off  | 00000000:82:00.0 Off |                    0 |
| N/A   31C    P0    37W / 250W |  14869MiB / 16280MiB |     99%      Default |
+-------------------------------+----------------------+----------------------+

+-----------------------------------------------------------------------------+
| Processes:                                                       GPU Memory |
|  GPU       PID   Type   Process name                             Usage      |
|=============================================================================|
|    0    157322      C   /home/cc/anaconda3/bin/python3.6           14859MiB |
|    1    157390      C   /home/cc/anaconda3/bin/python3.6           14859MiB |

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.04' --attack_iters 300 --batch_size 3584 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
[1] 25960
ady@skr-compute1:~/code/bandlimited-cnns/cnns/nnlib/robustness/batch_attack$ echo ${timestamp}.txt
2020-01-15-04-47-51-999248400.txt

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.1' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
nips

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=1 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.05' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
nips

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.01' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
iclr

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=1 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.02' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
iclr

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=2 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.06' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
iclr

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=3 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.07' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
iclr

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.03' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
wifi

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=1 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.045' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
wifi

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.0-model-0.01' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
icml2

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=1 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.0-model-0.02' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
icml2


timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.01-model-0.0' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
icml1
[1] 83466
cc@icml1:~/code/bandlimited-cnns/cnns/nnlib/robustness/batch_attack$ echo ${timestamp}.txt
2020-01-15-14-09-42-155628870.txt

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=1 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.02-model-0.0' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
[2] 83619
cc@icml1:~/code/bandlimited-cnns/cnns/nnlib/robustness/batch_attack$ echo ${timestamp}.txt
2020-01-15-14-10-33-761795890.txt

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.03-model-0.0' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
iclr

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=1 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.04-model-0.0' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=2 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.045-model-0.0' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=3 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.05-model-0.0' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.06-model-0.0' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
wifi

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=1 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.07-model-0.0' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt


timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.0-model-0.0' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
nips

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=1 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.005-model-0.0' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.01-model-0.0' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt
icml2

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=1 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.01-model-0.0' --attack_iters 200 --batch_size 2048 --limit_batch_number 0 --c 0.001 0.0005 0.0001 0.0 100.0 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 0.03 0.02 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt

timestamp=$(date +%Y-%m-%d-%H-%M-%S-%N)
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=../../../../ nohup /home/${USER}/anaconda3/bin/python3.6 attack.py --channel 'empty' --noise_epsilons 0.0 --net_mode 'perturb-0.01-model-0.0' --attack_iters 200 --batch_size 3584 --limit_batch_number 0 --c 0.02 0.03 0.01 0.005 0.001 0.0005 0.0001 0.0 100.0 10.0 2.0 1.0 0.5 0.4 0.3 0.2 0.1 0.07 0.05 0.04 >> ${timestamp}.txt 2>&1 &
echo ${timestamp}.txt