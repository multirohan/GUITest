import streamlit as st
import paho.mqtt.client as mqtt
import threading
import time
import json
import os
import csv
from datetime import datetime

# === PAGE CONFIG & GLOBAL STYLES ===
st.set_page_config(
    page_title="Multiscale SMART SPT Controller",
    layout="wide"
)

st.markdown("""
    <style>
      /* Reduce the default side and top padding */
      .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
        padding-top: 1.5rem;
      }
    </style>
    """, unsafe_allow_html=True)

# === MQTT CONFIG ===
MQTT_BROKER = os.getenv("MQTT_BROKER", "raspberrypi.local")  # or IP
MQTT_PORT   = 1883
MQTT_USER   = "myuser"      # remove or comment out if not required on 1883
MQTT_PASS   = "sptgoat"     # remove or comment out if not required
CMD_TOPIC = 'teensy/command'
LOG_TOPIC = 'teensy/log'
received_logs = []

# === MQTT CALLBACKS ===
def on_connect(client, userdata, flags, rc):
    client.subscribe(LOG_TOPIC)

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    received_logs.append(payload)

# --- Initialize MQTT Client ---
client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASS)   # only if you need auth
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, 1883, 60)
client.loop_start()

# --- LOG STATE ---
if 'log' not in st.session_state:
    st.session_state.log = []

# --- Sidebar: Material, Batch, Presets ---
st.sidebar.header("Job Info")
material = st.sidebar.selectbox("Material", ["Steel","Aluminum","Titanium","Kryptonite"])
batch    = st.sidebar.text_input("Batch Name")

st.sidebar.markdown("---")
if st.sidebar.button("Save Preset"):
    preset = {
        "material": material,
        "batch": batch,
        "enabled":  [st.session_state.get(f"run_{i}", False) for i in range(1,4)],
        "stages":   [st.session_state.get(f"stage_{i}") for i in range(1,4)],
        "speeds":   [st.session_state.get(f"speed_{i}") for i in range(1,4)],
        "cycles":   [st.session_state.get(f"cycles_{i}") for i in range(1,4)],
    }
    fname = st.sidebar.text_input("Preset filename", value="preset.json")
    if fname:
        with open(fname, "w") as f:
            json.dump(preset, f, indent=2)
        st.sidebar.success(f"Saved {fname}")
        st.session_state.log.append(f"Preset saved: {fname}")

preset_file = st.sidebar.file_uploader("Load Preset", type="json")
if preset_file:
    pr = json.load(preset_file)
    st.session_state.update({
        "material": pr.get("material", material),
        "batch":    pr.get("batch", batch),
    })
    for i in range(1,4):
        st.session_state[f"run_{i}"]    = pr["enabled"][i-1]
        st.session_state[f"stage_{i}"]  = pr["stages"][i-1]
        st.session_state[f"speed_{i}"]  = pr["speeds"][i-1]
        st.session_state[f"cycles_{i}"] = pr["cycles"][i-1]
    st.sidebar.success("Preset loaded")
    st.session_state.log.append("Preset loaded.")

# --- Main layout: controls left (80%), log right (20%) ---
main_col, log_col = st.columns([4, 1])

with main_col:
    cols = st.columns([1, 0.2, 1, 0.2, 1])
    for idx, col in zip(range(1, 6, 2), [cols[0], cols[2], cols[4]]):
        stage_num = (idx+1)//2
        with col:
            st.markdown("<div style='height: 5px'></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align:center'>", unsafe_allow_html=True)
            run_key = f"run_{stage_num}"
            if run_key not in st.session_state:
                st.session_state[run_key] = False
            btn_label = "Running" if st.session_state[run_key] else "Run"
            btn_id = f"run_btn_{stage_num}"
            custom_btn_css = f"""
                <style>
                .stButton > button#{btn_id} {{
                    width: 100%;
                    padding: 0.7em 0;
                    font-size: 1.3em;
                    font-weight: bold;
                    border: none;
                    border-radius: 8px;
                    margin-bottom: 0.5em;
                    cursor: pointer;
                    transition: background 0.2s;
                    background: {'#388e3c' if st.session_state[run_key] else '#d32f2f'};
                    color: white;
                }}
                </style>
            """
            st.markdown(custom_btn_css, unsafe_allow_html=True)
            if st.button(btn_label, key=btn_id):
                st.session_state[run_key] = not st.session_state[run_key]
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align:center'><span style='font-size:1.05em;font-weight:bold;'>Stage</span></div>", unsafe_allow_html=True)
            default_stage = ["P1","P2","P3"][stage_num-1]
            st.selectbox(
                " ", ["P1","P2","P3"],
                key=f"stage_{stage_num}",
                index=["P1","P2","P3"].index(st.session_state.get(f"stage_{stage_num}", default_stage)),
                label_visibility="collapsed",
                format_func=lambda x: f"  {x}  ",
                help="Select polisher stage"
            )
            st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
            st.markdown("<span style='font-size:1.05em;font-weight:bold;'>Speed (Hz)</span>", unsafe_allow_html=True)
            st.slider(" ", 1000, 40000, st.session_state.get(f"speed_{stage_num}", 10000), step=100, key=f"speed_{stage_num}", label_visibility="collapsed")
            st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)
            st.markdown("<span style='font-size:1.05em;font-weight:bold;'>Cycles</span>", unsafe_allow_html=True)
            st.slider(" ", 1, 50, st.session_state.get(f"cycles_{stage_num}", 1), step=1, key=f"cycles_{stage_num}", label_visibility="collapsed")
            st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)

    if st.button("Start Polishing"):
        st.write("✅ Sending commands via MQTT…")
        for i in range(1,4):
            if st.session_state.get(f"run_{i}"):
                cmd = f"START:{st.session_state[f'stage_{i}']},{st.session_state[f'speed_{i}']},{st.session_state[f'cycles_{i}']}"
                try:
                    client.publish(CMD_TOPIC, cmd)
                    st.session_state.log.append(f"Sent: {cmd}")
                except Exception as e:
                    st.session_state.log.append(f"MQTT publish error: {e}")
                st.write(f"> {cmd}")
                time.sleep(0.1)
        st.success("All commands sent.")

with log_col:
    st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)
    if st.button("Clear Log"):
        st.session_state.log.clear()
    combined = st.session_state.log + received_logs[-200:]
    st.text_area("Log", value="\n".join(combined), height=500, key="log_box", disabled=True)

# --- Custom Styles ---
st.markdown("""
    <style>
    .run-btn { width: 100%; padding: 0.7em 0; font-size: 1.3em; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; transition: background 0.2s; }
    .run-btn-red { background: #d32f2f; color: white; }
    .run-btn-green { background: #388e3c; color: white; }
    .run-btn:active { filter: brightness(0.95); }
    div[data-testid="stSlider"] { min-width: 250px !important; max-width: 100% !important; }
    div[data-testid="stSlider"] input[type="range"], div[data-testid="stSlider"] .st-cg, div[data-testid="stSlider"] .st-c9 { height: 32px !important; min-height: 32px !important; }
    </style>
""", unsafe_allow_html=True)
