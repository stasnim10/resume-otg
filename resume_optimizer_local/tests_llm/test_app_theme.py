from streamlit.testing.v1 import AppTest

APP = '''
import streamlit as st
from app_theme import apply_theme, render_theme_control
apply_theme()
render_theme_control()
st.text_input("Draft role", key="draft_role")
'''


def test_theme_switch_keeps_draft_and_pending_consent():
    app = AppTest.from_string(APP)
    app.query_params["authorization_id"] = "pending-consent"
    app.run()
    app.text_input[0].set_value("Supply Chain Manager").run()
    app.radio[0].set_value("Night").run()
    assert not app.exception
    assert app.query_params["theme"] == ["night"]
    assert app.query_params["authorization_id"] == ["pending-consent"]
    assert app.text_input[0].value == "Supply Chain Manager"
    app.radio[0].set_value("Warm").run()
    assert app.query_params["theme"] == ["warm"]
    assert app.text_input[0].value == "Supply Chain Manager"


def test_unknown_theme_falls_back_to_warm():
    app = AppTest.from_string(APP)
    app.query_params["theme"] = "unknown"
    app.run()
    assert not app.exception
    assert app.radio[0].value == "Warm"
