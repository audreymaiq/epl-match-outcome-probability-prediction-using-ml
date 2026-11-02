import pandas as pd

from ml.training.walk_forward_cv import CVResult, WalkForwardCV


def test_default_walk_forward_split_evaluates_opening_rounds():
    rows = []
    for season_index, season in enumerate(("2022/23", "2023/24", "2024/25")):
        n_matches = 100 if season_index < 2 else 38
        for week in range(1, n_matches + 1):
            rows.append({
                "season_name": season,
                "match_week": week if week <= 38 else (week - 1) // 10 + 1,
                "match_datetime": pd.Timestamp("2022-08-01") + pd.Timedelta(
                    days=season_index * 365 + week
                ),
            })

    data = pd.DataFrame(rows)
    splits = WalkForwardCV().split(data)

    assert len(splits) == 1
    _, test_indices = splits[0]
    test_rows = data.iloc[test_indices]
    assert test_rows["season_name"].eq("2024/25").all()
    assert test_rows["match_week"].min() == 1
    train_indices, test_indices = splits[0]
    train_end = data.iloc[train_indices]["match_datetime"].max()
    test_start = data.iloc[test_indices]["match_datetime"].min()
    assert train_end < test_start


def test_empty_walk_forward_summary_uses_json_safe_null_metrics():
    result = CVResult(n_folds=0)
    summary = result.summary

    assert summary["n_folds"] == 0
    assert summary["mean_accuracy"] is None
    assert summary["mean_log_loss"] is None
    assert summary["precision_D"] is None
    assert result.mean_accuracy is None
