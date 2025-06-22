import streamlit as st
import pandas as pd
import datetime
import folium
from streamlit_folium import st_folium
from ics import Calendar, Event
from geopy.distance import geodesic
import streamlit.components.v1 as components

# Page setup
st.set_page_config(page_title="Hawker Centre Open or Not? 🇸🇬", layout="wide")
st.title("Is the Hawker Centre Open or Not? 🍜")
st.markdown("Quickly check if your favourite hawker centre is closed due to cleaning or maintenance.")

# Load hawker data from CSV
@st.cache_data
def load_data():
    df = pd.read_csv("DatesofHawkerCentresClosure.csv")
    # Parse dates in DDMMYYYY format
    for q in ['q1', 'q2', 'q3', 'q4']:
        df[f'{q}_cleaningstartdate'] = pd.to_datetime(df[f'{q}_cleaningstartdate'].where(~df[f'{q}_cleaningstartdate'].astype(str).str.contains("TBC", na=False)), format='%d%m%Y', errors='coerce')
        df[f'{q}_cleaningenddate'] = pd.to_datetime(df[f'{q}_cleaningenddate'].where(~df[f'{q}_cleaningenddate'].astype(str).str.contains("TBC", na=False)), format='%d%m%Y', errors='coerce')
    df['other_works_startdate'] = pd.to_datetime(df['other_works_startdate'].where(~df['other_works_startdate'].astype(str).str.contains("TBC", na=False)), format='%d%m%Y', errors='coerce')
    df['other_works_enddate'] = pd.to_datetime(df['other_works_enddate'].where(~df['other_works_enddate'].astype(str).str.contains("TBC", na=False)), format='%d%m%Y', errors='coerce')
    return df

df = load_data()
today = datetime.date.today()

# Select hawker centre
centres = sorted(df['name'].unique())
selected = st.selectbox("Choose your hawker centre", centres)

# Filter selected centre data
selected_row = df[df['name'] == selected].iloc[0]

# Combine all closure periods
closures = []
for q in ['q1', 'q2', 'q3', 'q4']:
    start = selected_row[f'{q}_cleaningstartdate']
    end = selected_row[f'{q}_cleaningenddate']
    remarks = selected_row.get(f'remarks_{q}', '')
    if pd.notna(start) and pd.notna(end):
        closures.append({'start': start, 'end': end, 'remarks': remarks, 'type': 'Cleaning'})

# Add other works
if pd.notna(selected_row['other_works_startdate']) and pd.notna(selected_row['other_works_enddate']):
    closures.append({
        'start': selected_row['other_works_startdate'],
        'end': selected_row['other_works_enddate'],
        'remarks': selected_row.get('remarks_other_works', ''),
        'type': 'Other Works'
    })

# Convert closures to DataFrame
closure_df = pd.DataFrame(closures)

# Diagnostic feedback for missing or TBC closure dates
if closure_df.empty:
    st.warning("⚠️ This hawker centre has no confirmed closure dates available.")
elif closure_df['start'].isna().all() or closure_df['end'].isna().all():
    st.warning("⚠️ All closure periods for this hawker centre are marked as TBC or incomplete.")

# Status message
if not closure_df.empty and 'start' in closure_df.columns and 'end' in closure_df.columns:
    closed_today = closure_df[
        (closure_df['start'].dt.date <= today) & (closure_df['end'].dt.date >= today)
    ]
    if not closed_today.empty:
        st.error("🔦 Alamak! This hawker centre is CLOSED today.")
        st.dataframe(closed_today.style.applymap(lambda x: 'background-color: yellow' if isinstance(x, str) and 'TBC' in x else ''))
    else:
        st.success("✅ Steady lah! This hawker centre is OPEN today. Go makan!")
else:
    st.success("✅ Steady lah! This hawker centre is OPEN today. Go makan!")

# Upcoming closures
if not closure_df.empty and 'start' in closure_df.columns and 'end' in closure_df.columns:
    upcoming = closure_df[closure_df['start'].dt.date > today]
    if not upcoming.empty:
        st.info("🗓️ Upcoming closures:")
        st.dataframe(upcoming.style.applymap(lambda x: 'background-color: yellow' if isinstance(x, str) and 'TBC' in x else ''))
    else:
        st.success("✅ No upcoming closures. Go ahead and plan your makan trips!")
else:
    upcoming = pd.DataFrame()
    st.info("ℹ️ No closure data available for this hawker centre.")

# Favourites
if 'favourites' not in st.session_state:
    st.session_state['favourites'] = []

if st.button("⭐ Add to Favourites"):
    if selected not in st.session_state['favourites']:
        st.session_state['favourites'].append(selected)

if st.session_state['favourites']:
    st.sidebar.subheader("📆 Your Favourites")
    for fav in st.session_state['favourites']:
        st.sidebar.write(fav)

# Calendar export
if not upcoming.empty:
    cal = Calendar()
    for _, row in upcoming.iterrows():
        event = Event()
        event.name = f"{selected} - {row['type']}"
        event.begin = row['start']
        event.end = row['end']
        event.description = row['remarks']
        cal.events.add(event)
    st.download_button("📅 Export closures to calendar", cal.serialize(), "hawker_closures.ics")

# Suggest nearby open centres
st.subheader("📍 Nearby Open Centres")

lat, lon = selected_row['latitude_hc'], selected_row['longitude_hc']

df['distance'] = df.apply(lambda row: geodesic((lat, lon), (row['latitude_hc'], row['longitude_hc'])).km, axis=1)
nearby = df[(df['name'] != selected) & (df['distance'] < 2)]

# Check if today is within any closure period for nearby centres
def is_open_today(row):
    for q in ['q1', 'q2', 'q3', 'q4']:
        s = row[f'{q}_cleaningstartdate']
        e = row[f'{q}_cleaningenddate']
        if pd.notna(s) and pd.notna(e) and (s.date() <= today <= e.date()):
            return False
    s = row['other_works_startdate']
    e = row['other_works_enddate']
    if pd.notna(s) and pd.notna(e) and (s.date() <= today <= e.date()):
        return False
    return True

nearby['is_open'] = nearby.apply(is_open_today, axis=1)
nearby_open = nearby[nearby['is_open']]

if not nearby_open.empty:
    st.dataframe(nearby_open[['name', 'distance']].drop_duplicates().sort_values('distance'))
else:
    st.info("No nearby centres found within 2km that are open today.")

# Map of all hawker centres
st.subheader("🌍 Map View")

# Optional: use browser geolocation via JS (auto add user location to map)
user_lat = 1.3521
user_lon = 103.8198

with st.expander("📌 Click to allow browser to detect your location"):
    components.html("""
    <script>
    navigator.geolocation.getCurrentPosition(function(position) {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        const streamlitDoc = window.parent.document;
        streamlitDoc.querySelector('input[aria-label="Enter your latitude"]').value = lat;
        streamlitDoc.querySelector('input[aria-label="Enter your longitude"]').value = lon;
    });
    </script>
    """, height=100)

user_lat = st.number_input("Enter your latitude", value=user_lat, format="%.6f")
user_lon = st.number_input("Enter your longitude", value=user_lon, format="%.6f")

m = folium.Map(location=[user_lat, user_lon], zoom_start=12)

# Add user location
folium.Marker(
    location=[user_lat, user_lon],
    popup="📍 You are here",
    icon=folium.Icon(color='blue')
).add_to(m)

# Add hawker centre markers
for _, row in df.iterrows():
    marker_closed = not is_open_today(row)
    color = 'red' if marker_closed else 'green'
    folium.Marker(
        location=[row['latitude_hc'], row['longitude_hc']],
        popup=f"{row['name']} ({'Closed' if marker_closed else 'Open'})",
        icon=folium.Icon(color=color)
    ).add_to(m)

st_folium(m, width=700, height=500)

# Footer
st.markdown("---")
st.caption("© 2025 Made for Singaporean food lovers. Data from NEA / Data.gov.sg")
