#    A collection of tools to interface with manually traced and autosegmented
#    data in FAFB.
#
#    Copyright (C) 2019 Philipp Schlegel
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

import json
import navis
import os

from pathlib import Path
from importlib import reload

import cloudvolume as cv
import numpy as np

from .. import utils


__all__ = ['set_chunkedgraph_secret', 'get_chunkedgraph_secret']

FLYWIRE_DATASETS = {'production': 'fly_v31',
                    'sandbox': 'fly_v26'}


def get_chunkedgraph_secret(domain='prodv1.flywire-daf.com'):
    """Get chunked graph secret.

    Parameters
    ----------
    domain :    str
                Domain to get the secret for. Only relevant for
                ``cloudvolume>=3.11.0``.

    Returns
    -------
    token :     str

    """
    if hasattr(cv.secrets, 'cave_credentials'):
        token = cv.secrets.cave_credentials('prodv1.flywire-daf.com'
                                            ).get('token', None)
        if not token:
            raise ValueError(f'No chunkedgraph secret for domain {domain} '
                             'found. Please see '
                             'fafbseg.flywire.set_chunkedgraph_secret to set '
                             'your secret.')
    else:
        try:
            token = cv.secrets.chunkedgraph_credentials['token']
        except BaseException:
            raise ValueError('No chunkedgraph secret found. Please see '
                             'fafbseg.flywire.set_chunkedgraph_secret to set your '
                             'secret.')
    return token


def set_chunkedgraph_secret(token, filepath=None,
                            domain='prodv1.flywire-daf.com'):
    """Set chunked graph secret (called "cave credentials" now).

    Parameters
    ----------
    token :     str
                Get your token from
                https://globalv1.flywire-daf.com/auth/api/v1/refresh_token
    filepath :  str filepath
                Path to secret file. If not provided will store in default path:
                ``~/.cloudvolume/secrets/{domain}-cave-secret.json``
    domain :    str
                The domain (incl subdomain) this secret is for.

    """
    assert isinstance(token, str), f'Token must be string, got "{type(token)}"'

    if not filepath:
        filepath = f'~/.cloudvolume/secrets/{domain}-cave-secret.json'
    elif not filepath.endswith('/chunkedgraph-secret.json'):
        filepath = os.path.join(filepath, f'{domain}-cave-secret.json')
    elif not filepath.endswith('.json'):
        filepath = f'{filepath}.json'

    filepath = Path(filepath).expanduser()

    # Make sure this file (and the path!) actually exist
    if not filepath.exists():
        if not filepath.parent.exists():
            filepath.parent.mkdir(parents=True)
        filepath.touch()

    with open(filepath, 'w+') as f:
        json.dump({'token': token}, f)

    # We need to reload cloudvolume for changes to take effect
    reload(cv.secrets)
    reload(cv)

    # Should also reset the volume after setting the secret
    global fw_vol
    fw_vol = None

    print("Token succesfully stored in ", filepath)


def parse_root_ids(x):
    """Parse root IDs.

    Always returns an array of integers.
    """
    if isinstance(x, navis.BaseNeuron):
        ids = [x.id]
    elif isinstance(x, navis.NeuronList):
        ids = x.id
    elif isinstance(x, (int, np.int)):
        ids = [x]
    else:
        ids = navis.utils.make_iterable(x)

    # Make sure we are working with proper numerical IDs
    try:
        return np.asarray(ids).astype(int)
    except ValueError:
        raise ValueError(f'Unable to convert given root IDs to integer: {ids}')
    except BaseException:
        raise


def parse_volume(vol, **kwargs):
    """Parse CloudVolume."""
    global fw_vol
    if 'CloudVolume' not in str(type(vol)):
        if not isinstance(vol, str):
            raise ValueError(f'Unable to initialize CloudVolume from "{type(vol)}"')

        if not utils.is_url(vol):
            # We are assuming this is the dataset
            # Map "production" and "sandbox" with to their correct designations
            vol = FLYWIRE_DATASETS.get(vol, vol)

            # Below is supposedly the "old" api (/1.0/)
            # vol = f'graphene://https://prodv1.flywire-daf.com/segmentation/1.0/{vol}'

            # This is the new url
            vol = f'graphene://https://prodv1.flywire-daf.com/segmentation/table/{vol}'

            # This might eventually become the new url
            # vol = f'graphene://https://prodv1.flywire-daf.com/segmentation_proc/table/{vol}'

        if not vol.startswith('graphene://'):
            vol = f'graphene://{vol}'

        #  Change default volume if necessary
        if not fw_vol or getattr(fw_vol, 'path', None) != vol:
            # Set and update defaults from kwargs
            defaults = dict(mip=0,
                            fill_missing=True,
                            use_https=True,  # this way google secret is not needed
                            progress=False)
            defaults.update(kwargs)

            # Check if chunkedgraph secret exists
            secret = os.path.expanduser('~/.cloudvolume/secrets/chunkedgraph-secret.json')
            if not os.path.isfile(secret):
                # If not secrets but environment variable use this
                if 'CHUNKEDGRAPH_SECRET' in os.environ and 'secrets' not in defaults:
                    defaults['secrets'] = {'token': os.environ['CHUNKEDGRAPH_SECRET']}

            fw_vol = cv.CloudVolume(vol, **defaults)
            fw_vol.path = vol
    else:
        fw_vol = vol
    return fw_vol


# Initialize without a volume
fw_vol = None
