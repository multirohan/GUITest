# gui_streamlit_mqtt.py

import streamlit as st
import paho.mqtt.client as mqtt
import threading
import time
import json
import os

# === PAGE CONFIG & GLOBAL STYLES ===
st.set_page_config(
    page_title="Multiscale SMART SPT Controller",
    layout="wide"
)
st.markdown("""
    <style>
      .block-container {padding:1rem 1rem 1.5rem;}
    </style>
    """, unsafe_allow_html=True)

# === MQTT CONFIG ===
MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.1.228")
MQTT_PORT   = int(os.getenv("MQTT_PORT",   1883))
CMD_TOPIC   = "teensy/command"
LOG_TOPIC   = "teensy/log"

received_logs = []  # buffer for incoming log messages

# ——— MQTT CALLBACKS ———
def on_connect(client, userdata, flags, rc):
    client.subscribe(LOG_TOPIC)

def on_message(client, userdata, msg):
    received_logs.append(msg.payload.decode())

# ——— START MQTT CLIENT ———
client = mqtt.Client()
client.on_connect  = on_connect
client.on_message  = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# ——— LOG STATE ———
if 'log' not in st.session_state:
    st.session_state.log = []

# ——— Sidebar: Material / Batch ———
st.sidebar.header("Job Info")
material = st.sidebar.selectbox("Material", ["Steel","Aluminum","Titanium","Kryptonite"])
batch    = st.sidebar.text_input("Batch Name")

# ——— Main UI ———
main_col, log_col = st.columns([4,1])

with main_col:
    # Three stages in columns 1/3/5
    cols = st.columns([1, .2, 1, .2, 1])
    for idx, col in zip(range(3), [cols[0], cols[2], cols[4]]):
        with col:
            run_key  = f"run_{idx}"
            stage_key= f"stage_{idx}"
            speed_key= f"speed_{idx}"
            cycle_key=f"cycle_{idx}"
            if run_key not in st.session_state:
                st.session_state[run_key] = False
            if stage_key not in st.session_state:
                st.session_state[stage_key] = ["P1","P2","P3"][idx]
            if speed_key not in st.session_state:
                st.session_state[speed_key] = 2000
            if cycle_key not in st.session_state:
                st.session_state[cycle_key] = 5

            # Run toggle button
            col.markdown(f"<div style='text-align:center'>", unsafe_allow_html=True)
            btn_label = "Running" if st.session_state[run_key] else "Run"
            btn_color = "#388e3c" if st.session_state[run_key] else "#d32f2f"
            if st.button(btn_label, key=run_key):
                st.session_state[run_key] = not st.session_state[run_key]
            col.markdown("</div>", unsafe_allow_html=True)

            # Stage selector
            st.selectbox("Stage", ["P1","P2","P3"],
                         key=stage_key, index=["P1","P2","P3"].index(st.session_state[stage_key]))

            # Speed slider
            st.slider("Speed (Hz)", 1000, 40000,
                      st.session_state[speed_key], step=100,
                      key=speed_key)

            # Cycles slider
            st.slider("Cycles", 1, 50,
                      st.session_state[cycle_key], step=1,
                      key=cycle_key)

    # Start button
    if st.button("Start Polishing"):
        for i in range(3):
            if st.session_state[f"run_{i}"]:
                cmd = f"START:{st.session_state[f'stage_{i}']}," \
                      f"{st.session_state[f'speed_{i}']}," \
                      f"{st.session_state[f'cycle_{i}']}"
                client.publish(CMD_TOPIC, cmd)
                st.session_state.log.append(f"Sent: {cmd}")
        st.success("Commands published.")

with log_col:
    st.write("### Log")
    combined = st.session_state.log + received_logs[-100:]
    st.text_area("", value="\n".join(combined),
                 height=500, key="log_box")

# Keep the app alive
while True:
    time.sleep(1)
