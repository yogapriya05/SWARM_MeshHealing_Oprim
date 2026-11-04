from backend.app.breakeven import BreakevenConfig, analyze


def test_breakeven_separates_peer_pairs_from_single_host_delivery():
    result = analyze(BreakevenConfig(exact_nodes=4, sampled_nodes=6, samples_per_count=2))
    rows = result["cases"]["4"]["counts"]

    assert rows[1]["peer_probability"] == 0
    assert rows[2]["peer_worst_case"] == 1
    assert rows[1]["delivery_best_case"] == 1
    assert result["cases"]["6"]["counts"][1]["trials"] == 2
    assert result["definition"]["geometry"].startswith("Frozen")
