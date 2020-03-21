import numpy as np
import nibabel as nib
from tqdm import tqdm
from nilearn import image, masking, signal
from nistats.design_matrix import _cosine_drift as dct_set
from .utils import _load_gifti


def preprocess_func(funcs, mask, space, logger, high_pass=0.1, gm_thresh=0.9, tr=.7):
    """ Preprocesses a set of functional files (either volumetric nifti or
    surface gifti); high-pass filter (DCT) and normalization only.

    Parameters
    ----------
    funcs : list
        List of paths to functional files
    mask : str
        Path to mask (for now: assume it's a GM probseg file)
    space : str
        Name of space ('T1w', 'fsaverage{5,6}', 'MNI152NLin2009cAsym')
    logger : logging object
        Main logger (from cli.py)
    high_pass : float
        High-pass cutoff (in Hz)
    gm_thresh : float
        Gray matter probability threshold (higher = included in binary mask)
    tr : float
        TR of scan (only relevant if space is fsaverage) in seconds

    Returns
    -------
    data_ : np.ndarray
        2D array (time x voxels) with run-wise concatenated data
    run_idx_ : np.ndarray
        1D array with run indices, [0, 0, 0, ... , 1, 1, 1, ... , R, R, R]
        for R runs
    """

    if 'fs' not in space:  # no need for mask in surface files
        if mask is None:  # use functional brain masks
            logger.info("Creating mask by intersection of function masks")
            fmasks = [f.replace('desc-preproc_bold', 'desc-brain_mask') for f in funcs]
            mask = masking.intersect_masks(fmasks, threshold=0.8)
        else:
            # Using provided masks
            logger.info("Creating mask using GM probability map")

            # Downsample (necessary by default)
            mask = image.resample_to_img(mask, funcs[0])
            mask_data = mask.get_fdata()

            # Threshold
            mask_data = (mask_data >= gm_thresh).astype(int)
            mask = nib.Nifti1Image(mask_data, affine=mask.affine)
    else:
        # If fsaverage{5,6} space, don't use any mask
        mask = None

    logger.info("Starting preprocessing of functional data ... \n")
    data_, run_idx_ = [], []
    for i, func in enumerate(tqdm(funcs)):

        # Load data
        if 'fs' in space:  # assume gifti
            data = _load_gifti(func)
        else:
            # Mask data and extract stuff
            data = masking.apply_mask(func, mask)
            hdr = nib.load(func).header
            tr = hdr['pixdim'][4]

        # By now, data is a 2D array (time x voxels)
        n_vol = data.shape[0]
        frame_times = np.linspace(0.5 * tr, n_vol * (tr + 0.5), n_vol, endpoint=False)    

        # Create high-pass filter set
        hp_set = dct_set(high_pass, frame_times)[:, :-1]  # remove intercept

        # Clean data + save     
        data = signal.clean(data, detrend=True, standardize='zscore', confounds=hp_set)
        data_.append(data)

        # Add to run index
        run_idx_.append(np.ones(n_vol) * i)

    # Concatenate data in time dimension (or should we keep it in lists?)
    data_ = np.vstack(data_)
    run_idx_ = np.concatenate(run_idx_)

    print('')  # for clean interface

    logger.info(
        f"HP-filtered/normalized data has {data_.shape[0]} timepoints "
        f"(across {len(funcs)} runs) and {data_.shape[1]} voxels"
    )

    return data_, run_idx_


def preprocess_conf(confs, ricors):
    """ Preprocesses confounds by doing the following:
    1. Horizontal concatenation of Fmriprep confounds and RETROICOR (if any)
    2. Set NaNs to 0
    3. High-pass the data (same as functional data)
    4. PCA

    Parameters
    ----------

    Returns
    -------

    """
    pass