from download_verifier.confine import NoopConfiner, ProdConfiner


def test_noop_confiner_does_nothing() -> None:
    # le NoopConfiner ne pose AUCUN filtre : __call__ retourne None (ligne réelle couverte).
    assert NoopConfiner()() is None


def test_prod_confiner_constructs() -> None:
    # le constructeur n'est pas pragma ; __call__ (vrai seccomp) l'est.
    assert isinstance(ProdConfiner(), ProdConfiner)
