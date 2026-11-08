"""stub: terminal colours are cosmetic (colorama is not installed in this container)"""
class _C:
    def __getattr__(self, k): return ''
Fore = _C(); Style = _C(); Back = _C()
def init(*a, **k): pass
