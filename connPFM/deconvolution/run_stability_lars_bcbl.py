import os
import shutil
import numpy as np
import subprocess
import time


def bget(cmd):
    from subprocess import Popen, PIPE
    from sys import stdout
    from shlex import split

    out = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    (stdout, stderr) = out.communicate()
    return stdout.decode().split()


# Check if temp directory exists
def run_stability_lars(data, hrf, temp, jobs, username, niter, maxiterfactor):

    nscans = data.shape[0]
    nvoxels = data.shape[1]

    # Create temp folder if it doesn't exist
    os.makedirs(temp, exist_ok=True)

    # Save data into memmap object
    data_filename = os.path.join(temp, "data.npy")
    np.save(data_filename, data)

    # Save HRF to disk
    filename_hrf = os.path.join(temp, "hrf.npy")
    np.save(filename_hrf, hrf)

    # Calculates number of TE
    nTE = int(hrf.shape[0] / nscans)

    last = 0
    print("Numer of voxels: {}".format(nvoxels))

    for job_idx in range(jobs):
        jobs_left = jobs - job_idx
        voxels_left = nvoxels - last
        voxels_job = int(np.ceil(voxels_left / jobs_left))
        if job_idx == 0:
            first = 0
            last = first + voxels_job - 1
        elif job_idx != (jobs - 1):
            first = last + 1
            last = first + voxels_job - 1
        elif job_idx == (jobs - 1):
            first = last + 1
            last = nvoxels
        print("First voxel: {}".format(first))
        print("Last voxel: {}".format(last))

        jobname = "lars" + str(job_idx)
        input_parameters = "--data {} --hrf {} --nscans {} --maxiterfactor {} --nsurrogates {} --nte {} --mode {} --tempdir {} --first {} --last {} --voxels {} --n_job {}".format(
            data_filename,
            filename_hrf,
            str(nscans),
            str(maxiterfactor),
            niter,
            nTE,
            str(1),
            temp,
            int(first),
            int(last),
            nvoxels,
            job_idx,
        )
        subprocess.call(
            "qsub "
            + " -N "
            + jobname
            + ' -v INPUT_ARGS="'
            + input_parameters
            + '"'
            + " /bcbl/home/public/PARK_VFERRER/PFM/Scripts/compute_slars.sh",
            shell=True,
        )

        while int(
            bget(
                "qstat -u "
                + username
                + " | grep -v C | grep -c short"
                + username
            )[0]
        ) > (jobs - 1):
            time.sleep(1)

    while (
        int(
            bget(
                "qstat -u "
                + username
                + " | grep -F 'lars' | grep -c "
                + username
            )[0]
        )
        > 0
    ):
        time.sleep(0.5)

    for job_idx in range(jobs):
        auc_filename = temp + "/auc_" + str(job_idx) + ".npy"
        if job_idx == 0:
            auc = np.load(auc_filename)
        else:
            auc = np.hstack((auc, np.load(auc_filename)))

    return auc