import datetime
import getpass
import logging
import os
import socket
import subprocess
import sys

from nilearn.input_data import NiftiLabelsMasker

from connPFM.cli.connPFM import _get_parser
from connPFM.deconvolution import stability_lars_caller
from connPFM.utils import atlas_mod, hrf_generator, surrogate_generator

LGR = logging.getLogger(__name__)
LGR.setLevel(logging.INFO)


def connPFM(
    data,
    atlas,
    output,
    tr,
    username,
    te=None,
    dir="temp",
    block=False,
    jobs=50,
    nsurrogates=50,
    nstability=50,
    percentile=95,
    maxiterfactor=0.3,
    hrf_shape="SPMG1",
    hrf_path=None,
):
    # args_str = str(options)[9:]
    # history_str = "[{username}@{hostname}: {date}] python debiasing.py with {arguments}".format(
    #     username=getpass.getuser(),
    #     hostname=socket.gethostname(),
    #     date=datetime.datetime.now().strftime("%c"),
    #     arguments=args_str,
    # )

    # kwargs = vars(options)
    # kwargs["history"] = history_str

    breakpoint()
    if te is None:
        te = [0]

    os.makedirs(dir, exist_ok=True)

    # TODO: make it multi-echo compatible
    LGR.info("Masking data...")
    atlas_old = atlas
    atlas = atlas_mod.transform(atlas, data, dir)
    masker = NiftiLabelsMasker(
        labels_img=atlas, standardize="psc", memory="nilearn_cache", strategy="mean"
    )
    data_masked = masker.fit_transform(data)
    LGR.info("Data masked.")

    LGR.info("Generating HRF...")
    # Generates HRF matrix
    hrf_matrix = hrf_generator.HRFMatrix(
        TR=tr,
        TE=te,
        nscans=data_masked.shape[0],
        r2only=True,
        block=block,
        is_afni=True,
        lop_hrf=hrf_shape,
        path=hrf_path,
    )
    hrf_matrix.generate_hrf()
    hrf = hrf_matrix.hrf_norm
    LGR.info("HRF generated.")

    LGR.info("Running stability selection on original data...")
    auc = stability_lars_caller(
        data=data_masked,
        hrf=hrf,
        temp=dir,
        jobs=jobs,
        username=username,
        niter=nstability,
        maxiterfactor=maxiterfactor,
    )
    LGR.info("Stability selection on original data finished.")

    LGR.info("Saving AUC results of original data...")
    auc_4d = masker.inverse_transform(auc)
    auc_4d.to_filename(output)
    atlas_mod.inverse_transform(output, data)
    LGR.info("AUC results on original data saved.")

    LGR.info("Updating file history...")
    subprocess.run('3dNotes -h "' + history_str + '" ' + output, shell=True)
    LGR.info("File history updated.")

    if nsurrogates:
        LGR.info(f"Performing PFM on {nsurrogates} surrogates...")
        LGR.info("Make yourself a cup of coffee while it runs :)")
        for n_sur in range(nsurrogates):
            # Generate surrogate
            surrogate_name = os.path.join(dir, f"surrogate_{n_sur}.nii.gz")
            surrogate_masked = surrogate_generator.generate_surrogate(
                data=data, atlas=atlas, atlas_orig=atlas_old, output=surrogate_name
            )
            # Calculate AUC
            auc = stability_lars_caller(
                data=surrogate_masked,
                hrf=hrf,
                temp=dir,
                jobs=jobs,
                username=username,
                niter=nstability,
                maxiterfactor=maxiterfactor,
            )

            # Transform back to 4D
            auc_4d = masker.inverse_transform(auc)

            # Save surrogate AUC
            surrogate_out = os.path.join(dir, f"surrogate_AUC_{n_sur}.nii.gz")
            auc_4d.to_filename(surrogate_out)
            atlas_mod.inverse_transform(surrogate_out, data)
            LGR.info(f"{n_sur}/{nsurrogates -1 }")

        LGR.info(f"PFM on {nsurrogates} surrogates finished.")

    LGR.info("PFM finished.")


def _main(argv=None):
    options = _get_parser().parse_args(argv)
    connPFM(**vars(options))


if __name__ == "__main__":
    _main(sys.argv[1:])
