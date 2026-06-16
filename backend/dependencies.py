import pandas as pd
from fastapi import Request


def get_df(request: Request) -> pd.DataFrame:
    return request.app.state.df


def get_id_map(request: Request) -> dict:
    return request.app.state.id_map
