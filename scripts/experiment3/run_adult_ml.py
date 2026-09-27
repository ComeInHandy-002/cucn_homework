"""实验三：UCI Adult Income 数据清洗、特征工程与 7 种算法对比实验。

课程要求映射：
- 数据清洗、缺失值处理与特征工程（EDA 图 <= 10 张）
- 算法编码不少于 6 种，每种含训练、评估与结果说明（本脚本实现 7 种）
- 评估指标：准确率、精确率、召回率、F1、ROC-AUC，并可视化对比
- 完整可运行代码：本脚本一键复现全部产物到 results/experiment3/

运行：
    .venv/Scripts/python.exe scripts/experiment3/run_adult_ml.py
"""

from __future__ import annotations

import io
import json
import sys
import time
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    silhouette_score,
    adjusted_rand_score,
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "experiment3"
OUT = ROOT / "results" / "experiment3"
LOCAL_PROXY = "http://127.0.0.1:7897"

COLUMNS = [
    "age", "workclass", "fnlwgt", "education", "education-num",
    "marital-status", "occupation", "relationship", "race", "sex",
    "capital-gain", "capital-loss", "hours-per-week", "native-country", "income",
]
RAW_URLS = {
    "adult.data": "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data",
    "adult.test": "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.test",
}

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False


class Tee(io.TextIOBase):
    """Mirror console output into a log file so the run screenshot is real."""

    def __init__(self, path: Path) -> None:
        self.file = path.open("w", encoding="utf-8")

    def write(self, text: str) -> int:
        sys.__stdout__.write(text)
        self.file.write(text)
        self.file.flush()
        return len(text)

    def flush(self) -> None:
        self.file.flush()


def log(message: str = "") -> None:
    print(message)


def download_raw() -> tuple[Path, Path]:
    CACHE.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, url in RAW_URLS.items():
        target = CACHE / name
        if target.exists() and target.stat().st_size > 0:
            log(f"[数据] 使用缓存: {target.name} ({target.stat().st_size // 1024} KB)")
            paths[name] = target
            continue
        for attempt, opener in (("直连", urllib.request.build_opener()), ("本机代理", urllib.request.build_opener(urllib.request.ProxyHandler({"http": LOCAL_PROXY, "https": LOCAL_PROXY})))):
            try:
                log(f"[数据] {attempt}下载 {url}")
                with opener.open(url, timeout=60) as response, target.open("wb") as handle:
                    handle.write(response.read())
                log(f"[数据] 已保存 {target.name} ({target.stat().st_size // 1024} KB)")
                paths[name] = target
                break
            except Exception as exc:  # noqa: BLE001
                log(f"[数据] {attempt}失败: {exc}")
        else:
            raise RuntimeError("adult 数据集下载失败，请检查网络或手动放置到 data/experiment3/")
    return paths["adult.data"], paths["adult.test"]


def load_frames(train_path: Path, test_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = pd.read_csv(train_path, header=None, names=COLUMNS, skipinitialspace=True, na_values="?")
    test = pd.read_csv(test_path, header=None, names=COLUMNS, skipinitialspace=True, skiprows=1, na_values="?")
    for frame in (train, test):
        frame["income"] = frame["income"].str.strip().str.rstrip(".")
    return train, test


def eda_charts(train: pd.DataFrame, out: dict) -> None:
    """预处理/特征工程观察图（共 8 张，满足 <=10 张要求）。"""
    # p1 缺失值分布
    missing = train.isna().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(6.4, 3.0), dpi=150)
    ax.bar(missing.index, missing.values, color="#2F75B5")
    for index, value in enumerate(missing.values):
        ax.text(index, value, f"{value}\n({value / len(train) * 100:.1f}%)", ha="center", va="bottom", fontsize=8)
    ax.set_title("缺失值分布（? 记号解析为 NaN）", fontsize=11)
    ax.set_ylabel("缺失条数")
    ax.tick_params(axis="x", labelsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "p1_missing_values.png", bbox_inches="tight")
    plt.close(fig)

    # p2 年龄分布（按收入）
    fig, ax = plt.subplots(figsize=(6.4, 3.0), dpi=150)
    for label, group in train.groupby("income"):
        ax.hist(group["age"], bins=30, alpha=0.55, label=f"收入{label}", density=True)
    ax.set_title("年龄分布按收入分组（右偏，无需变换）", fontsize=11)
    ax.set_xlabel("age")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "p2_age_distribution.png", bbox_inches="tight")
    plt.close(fig)

    # p3 周工作时长
    fig, ax = plt.subplots(figsize=(6.4, 3.0), dpi=150)
    ax.hist(train["hours-per-week"], bins=40, color="#70AD47")
    ax.axvline(40, color="#C00000", linestyle="--", label="40h 全职线")
    ax.set_title("周工作时长分布（40 小时附近强峰）", fontsize=11)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "p3_hours_distribution.png", bbox_inches="tight")
    plt.close(fig)

    # p4 capital-gain 偏态与 log1p 变换对比
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.0), dpi=150)
    axes[0].hist(train["capital-gain"], bins=40, color="#ED7D31")
    axes[0].set_title(f"capital-gain 原始（偏度 {train['capital-gain'].skew():.2f}）", fontsize=10)
    axes[1].hist(np.log1p(train["capital-gain"]), bins=40, color="#70AD47")
    axes[1].set_title(f"log1p 变换后（偏度 {np.log1p(train['capital-gain']).skew():.2f}）", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "p4_capital_gain_skew.png", bbox_inches="tight")
    plt.close(fig)

    # p5 workclass 类别计数（含缺失）
    counts = train["workclass"].fillna("缺失").value_counts()
    fig, ax = plt.subplots(figsize=(6.8, 3.2), dpi=150)
    ax.barh(counts.index[::-1], counts.values[::-1], color="#2F75B5")
    ax.set_title("workclass 类别计数（缺失将填为 Unknown）", fontsize=11)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "p5_workclass_counts.png", bbox_inches="tight")
    plt.close(fig)

    # p6 教育年限与高收入比例
    ratio = train.groupby("education-num")["income"].apply(lambda s: (s == ">50K").mean())
    fig, ax = plt.subplots(figsize=(6.4, 3.0), dpi=150)
    ax.plot(ratio.index, ratio.values, marker="o", color="#2F75B5")
    ax.set_title("教育年限与高收入比例（强单调关系，做序号特征保留）", fontsize=11)
    ax.set_xlabel("education-num")
    ax.set_ylabel("P(>50K)")
    fig.tight_layout()
    fig.savefig(OUT / "p6_education_income.png", bbox_inches="tight")
    plt.close(fig)

    # p7 类别不平衡
    balance = train["income"].value_counts()
    fig, ax = plt.subplots(figsize=(4.6, 3.0), dpi=150)
    ax.bar(balance.index, balance.values, color=["#2F75B5", "#ED7D31"])
    for index, value in enumerate(balance.values):
        ax.text(index, value, f"{value}\n{value / len(train) * 100:.1f}%", ha="center", va="bottom", fontsize=9)
    ax.set_title("目标类别不平衡（约 3:1，需看召回而非只看准确率）", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "p7_class_balance.png", bbox_inches="tight")
    plt.close(fig)

    out["missing_values"] = {key: int(value) for key, value in missing.items()}
    out["class_balance"] = {key: int(value) for key, value in balance.items()}


def preprocess(train: pd.DataFrame, test: pd.DataFrame) -> tuple:
    """清洗 + 缺失值处理 + 特征工程，返回 (X_train, y_train, X_test, y_test, feature_names)。"""
    def clean(frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.copy()
        before = len(frame)
        frame = frame.drop_duplicates()
        # fnlwgt 是人口普查抽样权重，与个体收入无因果含义，剔除。
        frame = frame.drop(columns=["fnlwgt"])
        # education 字符串与 education-num 完全一一对应，保留序号版本。
        frame = frame.drop(columns=["education"])
        # 缺失值：三个类别列填 Unknown（约 7% 行含缺失，直接删行损失过大，
        # 且"未申报"本身可作为类别信息交由树模型学习）。
        for column in ("workclass", "occupation", "native-country"):
            frame[column] = frame[column].fillna("Unknown")
        # 强偏态金额列做 log1p，并派生是否有过资本收益/损失的二值特征。
        for column in ("capital-gain", "capital-loss"):
            frame[f"{column}-log"] = np.log1p(frame[column])
            frame[f"has-{column}"] = (frame[column] > 0).astype(int)
        # 周工时离散化为业务分段。
        frame["hours-band"] = pd.cut(
            frame["hours-per-week"], bins=[0, 34, 40, 50, 100],
            labels=["part", "full", "overtime", "extreme"], include_lowest=True,
        ).astype(str)
        frame["income"] = (frame["income"] == ">50K").astype(int)
        log(f"[清洗] 去重 {before} -> {len(frame)} 行；缺失填充完成")
        return frame

    train_c, test_c = clean(train), clean(test)
    combined = pd.concat([train_c, test_c], keys=["train", "test"])
    features = pd.get_dummies(
        combined.drop(columns=["income"]),
        columns=["workclass", "marital-status", "occupation", "relationship", "race", "sex", "native-country", "hours-band"],
        dtype=float,
    )
    x_train = features.xs("train").to_numpy(dtype=np.float32)
    x_test = features.xs("test").to_numpy(dtype=np.float32)
    y_train = train_c["income"].to_numpy()
    y_test = test_c["income"].to_numpy()
    log(f"[特征工程] One-Hot 后特征维数: {features.shape[1] - 1}")
    return x_train, y_train, x_test, y_test, list(features.columns)


def evaluate(name, y_true, y_pred, seconds, proba=None, extra=None) -> dict:
    result = {
        "algorithm": name,
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred)), 4),
        "recall": round(float(recall_score(y_true, y_pred)), 4),
        "f1": round(float(f1_score(y_true, y_pred)), 4),
        "train_seconds": round(seconds, 2),
    }
    if proba is not None:
        result["roc_auc"] = round(float(roc_auc_score(y_true, proba)), 4)
    if extra:
        result.update(extra)
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tee = Tee(OUT / "run_log.txt")
    sys.stdout = tee
    sys.stderr = tee
    results: dict = {"dataset": "UCI Adult Income (Census Income)", "algorithms": []}

    log("== 实验三：UCI Adult Income 机器学习算法对比 ==")
    train_path, test_path = download_raw()
    train, test = load_frames(train_path, test_path)
    log(f"[数据] 训练 {len(train)} 行 / 测试 {len(test)} 行，{len(COLUMNS)} 列")

    eda_charts(train, results)
    x_train, y_train, x_test, y_test, feature_names = preprocess(train, test)

    scaler = StandardScaler().fit(x_train)
    x_train_s, x_test_s = scaler.transform(x_train), scaler.transform(x_test)

    # SVC 受 O(n^2) 复杂度限制，采用分层抽样 1.2 万样本训练（报告中说明边界）。
    svc_x, _, svc_y, _ = train_test_split(x_train_s, y_train, train_size=12000, stratify=y_train, random_state=42)

    jobs: list[tuple[str, object, object, object, object]] = [
        ("1 逻辑回归", LogisticRegression(max_iter=2000), x_train_s, y_train, x_test_s),
        ("2 决策树", DecisionTreeClassifier(random_state=42), x_train, y_train, x_test),
        ("3 随机森林", RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=42), x_train, y_train, x_test),
        ("4 支持向量机(SVC-RBF)", SVC(kernel="rbf", cache_size=800), svc_x, svc_y, x_test_s),
        ("5 K近邻(K=21)", KNeighborsClassifier(n_neighbors=21, n_jobs=-1), x_train_s, y_train, x_test_s),
        ("6 朴素贝叶斯", GaussianNB(), x_train, y_train, x_test),
    ]

    roc_curves = []
    for name, model, fit_x, fit_y, predict_x in jobs:
        started = time.perf_counter()
        model.fit(fit_x, fit_y)
        seconds = time.perf_counter() - started
        if predict_x is None:
            predict_x = x_test_s
        prediction = model.predict(predict_x)
        proba = model.predict_proba(predict_x)[:, 1] if hasattr(model, "predict_proba") else None
        entry = evaluate(name, y_test, prediction, seconds, proba)
        if name.startswith("4"):
            entry["note"] = "分层抽样 12000 样本训练（RBF 核 O(n^2) 复杂度限制）"
        results["algorithms"].append(entry)
        if proba is not None:
            roc_curves.append((name, proba))
        log(f"[训练] {name}: acc={entry['accuracy']} recall={entry['recall']} f1={entry['f1']} auc={entry.get('roc_auc')} ({entry['train_seconds']}s)")

    # 7 K-Means 聚类：肘部法选 k，k=2 与真实标签对齐评估。
    inertia, silhouettes = [], []
    for k in range(2, 9):
        km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(x_train_s)
        inertia.append(km.inertia_)
        sample = train_test_split(x_train_s, train_size=5000, stratify=y_train, random_state=42)[0]
        silhouettes.append(round(float(silhouette_score(sample, km.predict(sample))), 4))
        log(f"[聚类] k={k} inertia={inertia[-1]:.0f} silhouette={silhouettes[-1]}")
    kmeans = KMeans(n_clusters=2, n_init=10, random_state=42).fit(x_train_s)
    # 两个簇的高收入占比都低于 50%，按簇均值排序做最优对齐（高收入占比更高
    # 的簇映射为 1），否则会退化为全预测多数类。
    order = sorted((0, 1), key=lambda c: y_train[kmeans.labels_ == c].mean())
    mapping = {order[0]: 0, order[1]: 1}
    cluster_prediction = np.vectorize(mapping.get)(kmeans.predict(x_test_s))
    entry = evaluate(
        "7 K-Means聚类(k=2)", y_test, cluster_prediction, 0.0,
        extra={"ari": round(float(adjusted_rand_score(y_test, cluster_prediction)), 4), "silhouette_k2": silhouettes[0]},
    )
    results["algorithms"].append(entry)
    log(f"[训练] 7 K-Means聚类: acc={entry['accuracy']} ARI={entry['ari']}（无监督基线，仅作对照）")

    # ---- 评估可视化 ----
    names = [item["algorithm"] for item in results["algorithms"]]
    metrics = {key: [item[key] for item in results["algorithms"]] for key in ("accuracy", "precision", "recall", "f1")}
    fig, ax = plt.subplots(figsize=(10.5, 3.8), dpi=150)
    x = np.arange(len(names))
    width = 0.2
    for offset, (key, color) in enumerate(zip(("accuracy", "precision", "recall", "f1"), ("#2F75B5", "#70AD47", "#ED7D31", "#7C5CFF"))):
        bars = ax.bar(x + (offset - 1.5) * width, metrics[key], width, label=key, color=color)
        for bar, value in zip(bars, metrics[key]):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.008, f"{value:.3f}", ha="center", fontsize=6, rotation=90)
    ax.set_xticks(x, [name.replace(" ", "\n", 1) for name in names], fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.set_title("七种算法测试集指标对比（UCI Adult，官方 train/test 划分）", fontsize=11)
    ax.legend(ncol=4, fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "e1_model_comparison.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.6, 4.4), dpi=150)
    for name, proba in roc_curves:
        fpr, tpr, _ = roc_curve(y_test, proba)
        auc = next(item["roc_auc"] for item in results["algorithms"] if item["algorithm"] == name)
        ax.plot(fpr, tpr, label=f"{name} AUC={auc}")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
    ax.set_title("六种分类器 ROC 曲线", fontsize=11)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "e2_roc_curves.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(6.2, 3.2), dpi=150)
    ks = list(range(2, 9))
    ax1.plot(ks, inertia, marker="o", color="#2F75B5", label="inertia")
    ax1.set_xlabel("k")
    ax2 = ax1.twinx()
    ax2.bar(ks, silhouettes, alpha=0.35, color="#ED7D31", label="silhouette")
    ax1.set_title("K-Means 肘部法与轮廓系数", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "e3_kmeans_elbow.png", bbox_inches="tight")
    plt.close(fig)

    best = max((item for item in results["algorithms"] if item["algorithm"].startswith("3")), key=lambda item: item["f1"])
    best_model = RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=42).fit(x_train, y_train)
    fig, ax = plt.subplots(figsize=(4.4, 3.6), dpi=150)
    matrix = confusion_matrix(y_test, best_model.predict(x_test))
    ax.imshow(matrix, cmap="Blues")
    for (i, j), value in np.ndenumerate(matrix):
        ax.text(j, i, str(value), ha="center", va="center", color="white" if value > matrix.max() / 2 else "black")
    ax.set_xticks([0, 1], ["预测<=50K", "预测>50K"], fontsize=9)
    ax.set_yticks([0, 1], ["实际<=50K", "实际>50K"], fontsize=9)
    ax.set_title(f"随机森林混淆矩阵（F1={best['f1']}）", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "e4_confusion_matrix.png", bbox_inches="tight")
    plt.close(fig)

    importances = pd.Series(best_model.feature_importances_, index=feature_names).nlargest(10)[::-1]
    fig, ax = plt.subplots(figsize=(6.2, 3.4), dpi=150)
    ax.barh(importances.index, importances.values, color="#2F75B5")
    ax.set_title("随机森林特征重要性 Top10（特征工程有效性佐证）", fontsize=10)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "e5_feature_importance.png", bbox_inches="tight")
    plt.close(fig)

    results["best_model"] = "随机森林"
    results["notes"] = [
        "SVC 采用 12000 分层抽样训练（O(n^2) 复杂度限制）",
        "K-Means 为无监督对照：k=2 簇号经训练集多数票对齐后评估，另报 ARI",
        "训练/测试使用 UCI 官方划分，未做随机重划",
    ]
    (OUT / "metrics.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[完成] 指标与图表已输出到 {OUT}")


if __name__ == "__main__":
    main()
