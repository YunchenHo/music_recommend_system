from sklearn.preprocessing import LabelEncoder
import numpy as np
import pandas as pd


def preprocess_members(members: pd.DataFrame) -> tuple[pd.DataFrame, LabelEncoder]:
    complete_members = members[
        (members["bd"] >= 10) & (members["bd"] <= 80) & (members["gender"].notna())
    ].copy()

    msno_encoder = LabelEncoder()
    complete_members["msno_id"] = msno_encoder.fit_transform(complete_members["msno"])
    complete_members = complete_members.drop(columns=["msno"]).reset_index(drop=True)

    bins = [-1, 0, 12, 18, 25, 35, 50, 80]
    labels = [0, 1, 2, 3, 4, 5, 6]
    complete_members["bd_group"] = pd.cut(
        complete_members["bd"], bins=bins, labels=labels
    ).astype("int8")
    complete_members = complete_members.drop(columns=["bd"])

    complete_members = pd.get_dummies(
        complete_members, columns=["gender"], prefix="gender", dtype="int8"
    )

    complete_members["registration_init_time"] = pd.to_datetime(
        complete_members["registration_init_time"], format="%Y%m%d", errors="coerce"
    )
    complete_members["expiration_date"] = pd.to_datetime(
        complete_members["expiration_date"], format="%Y%m%d", errors="coerce"
    )

    complete_members["registration_year"] = (
        complete_members["registration_init_time"].dt.year.astype("int16")
    )
    complete_members["membership_days"] = (
        complete_members["expiration_date"] - complete_members["registration_init_time"]
    ).dt.days
    complete_members["membership_days"] = (
        complete_members["membership_days"].clip(lower=0).fillna(0)
    )

    bins = [0, 30, 180, 365, 730, 1825, 3650, np.inf]
    labels = [0, 1, 2, 3, 4, 5, 6]
    complete_members["membership_group"] = pd.cut(
        complete_members["membership_days"],
        bins=bins,
        labels=labels,
        include_lowest=True,
    ).astype("int8")

    complete_members = complete_members.drop(
        columns=["registration_init_time", "expiration_date"]
    )

    complete_members["city"] = complete_members["city"].astype("int8")
    complete_members["registered_via"] = complete_members["registered_via"].astype(
        "int8"
    )

    city_counts = complete_members["city"].value_counts().sort_values(ascending=False)
    complete_members["city_count"] = (
        complete_members["city"].map(city_counts).astype("int32")
    )

    return complete_members, msno_encoder
