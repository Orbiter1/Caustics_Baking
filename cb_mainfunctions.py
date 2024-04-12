from datetime import datetime
import math
import numpy as np


def compute_caustic_map(target_map, coordinates, colors, texture_res, colored, index, pano, sample_res, sampler_fov,
                        normalization, debug):
    # data cleanup
    valid = (coordinates[:, 2] > 0) & (coordinates[:, 0] > 0) & (coordinates[:, 0] < 1) & (coordinates[:, 1] > 0) & (
            coordinates[:, 1] < 1)
    if colored:
        if pano:
            lens_time = datetime.now()
            colors *= fix_pano_lens(sample_res, sampler_fov)
        colors = colors[np.where(valid)]
    elif pano:
        lens_time = datetime.now()
        coordinates[:, 2] *= fix_pano_lens(sample_res, sampler_fov).reshape(-1, )

    coordinates = coordinates[np.where(valid)]
    if len(coordinates) == 0:
        return

    # converting from UV to Pixel coordinates
    coordinates = coordinates * [texture_res, texture_res, 1, 1]

    coordinates[:, [0, 1]] = np.floor(coordinates[:, [0, 1]])
    coordinates = coordinates * [1, texture_res, 1, 1]
    coordinates[:, [0]] = np.floor(coordinates[:, [0]])

    data = coordinates[:, 2]
    coordinates = (coordinates[:, [1]] + coordinates[:, [0]]).astype(int)

    order = np.lexsort(coordinates.T)
    diff = np.diff(coordinates[order], axis=0)
    uniq_mask = np.append(True, (diff != 0).any(axis=1))

    uniq_inds = order[uniq_mask]
    inv_idx = np.zeros_like(order)
    inv_idx[order] = np.cumsum(uniq_mask) - 1

    if colored:
        r = np.bincount(inv_idx, weights=np.reshape(colors[:, [0]], -1))
        g = np.bincount(inv_idx, weights=np.reshape(colors[:, [1]], -1))
        b = np.bincount(inv_idx, weights=np.reshape(colors[:, [2]], -1))
        data = np.vstack((r, g, b, r)).T
    else:
        data = np.bincount(inv_idx, weights=data)
        data = np.vstack((data, data, data, data)).T

    data = data * normalization
    coordinates = coordinates[uniq_inds]
    target_map[coordinates] += data.reshape(-1, 1, 4)
    return


def fix_pano_lens(sample_res, fov):
    a = math.sin(fov * 0.5)
    r = np.fromfunction(
        lambda x, y: (((x - sample_res * .5 + .5) ** 2 + (y - sample_res * .5 + .5) ** 2) ** .5) / sample_res * 2 + 0.0001,
        (sample_res, sample_res), dtype=float).reshape(-1, 1)
    return (np.sin(r * fov * 0.5) / (r * a)) ** 2
