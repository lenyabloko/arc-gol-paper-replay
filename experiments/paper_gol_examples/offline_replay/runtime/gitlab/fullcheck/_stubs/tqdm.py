"""stub: progress bars are cosmetic (tqdm is not installed in this container)"""
def tqdm(it=None, *a, **k):
    return it if it is not None else []
