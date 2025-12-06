import streamlit as st
import pandas as pd
import altair as alt
from supabase import create_client
from datetime import datetime
from streamlit_option_menu import option_menu

# ------------------------------------------------
# PREVENT LOGOUT ON REFRESH
# ------------------------------------------------
if "refresh" in st.session_state:
    del st.session_state["refresh"]

# ------------------------------------------------
# CONFIG
# ------------------------------------------------
st.set_page_config(page_title="Business Dashboard", layout="centered")

# ---- Load Lottie animation ----
def load_lottiefile(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

if "show_intro" not in st.session_state:
    st.session_state.show_intro = True

if st.session_state.show_intro:
    lottie_intro = load_lottiefile("Revenue.json")
    splash = st.empty()
    with splash.container():
        st.markdown("<h1 style='text-align:center;'>WELCOME to Business app</h1>", unsafe_allow_html=True)
        st_lottie(lottie_intro, height=350, speed=1.0, loop=False)
        time.sleep(3)
    splash.empty()
    st.session_state.show_intro = False

SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase credentials missing in secrets.toml")
    st.stop()

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ------------------------------------------------
# AUTH FUNCTIONS
# ------------------------------------------------
def supabase_sign_in(email, password):
    try:
        result = sb.auth.sign_in_with_password({"email": email, "password": password})
        if result.user:
            st.session_state["user"] = result.user
            st.session_state["email"] = email
            return True, result.user
        return False, "Login failed."
    except Exception as e:
        return False, str(e)

def logout():
    st.session_state.clear()
    st.rerun()

# ------------------------------------------------
# LOGIN SCREEN (NO SIGNUP)
# ------------------------------------------------
def login_screen():
    st.title("🔐 Login to Business Dashboard")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    login_btn = st.button("Login")

    if login_btn:
        if not email or not password:
            st.error("Please fill all fields.")
        else:
            ok, result = supabase_sign_in(email, password)
            if ok:
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid email or password")

# ------------------------------------------------
# DATA FETCHING HELPERS
# ------------------------------------------------
@st.cache_data(ttl=20)
def fetch_table(table_name: str):
    try:
        res = sb.table(table_name).select("*").execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Error fetching {table_name}: {e}")
        return pd.DataFrame()

def parse_dates(df: pd.DataFrame, col: str):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

# ------------------------------------------------
# MAIN DASHBOARD
# ------------------------------------------------
def dashboard():

    with st.sidebar:
        st.title("📌 Business Panel")

        section = option_menu(
            menu_title="Dashboard Menu",
            options=["📊 Sales Dashboard", "👥 Customer Details", "📦 Product Analytics"],
            icons=["bar-chart", "people-fill", "box"],
            default_index=0
        )

        st.markdown("---")

        # 🚀 Refresh button (keeps user logged in)
        if st.button("🔄 Refresh App"):
            st.session_state["refresh"] = True
            st.rerun()

        # Logout
        if st.button("🚪 Logout"):
            logout()

    # Load data
    with st.spinner("Fetching data..."):
        products_df = fetch_table("products")
        sales_df = fetch_table("sales")
        customers_df = fetch_table("customers")

    # Date parsing
    sales_df = parse_dates(sales_df, "date")
    customers_df = parse_dates(customers_df, "joined_on")

    if "joined_on" in customers_df.columns:
        customers_df = customers_df.rename(columns={"joined_on": "joined_at"})

    # ------------------------------------------------
    # SALES DASHBOARD
    # ------------------------------------------------
    if section == "📊 Sales Dashboard":
        st.title("📊 Sales Dashboard")

        col1, col2, col3 = st.columns(3)

        total_revenue = (
            sales_df["amount"].astype(float).sum() if not sales_df.empty else 0
        )
        total_orders = len(sales_df)
        last_sale = sales_df["date"].max() if not sales_df.empty else "—"

        col1.metric("Total Revenue", f"₹ {total_revenue:,.0f}")
        col2.metric("Total Orders", total_orders)
        col3.metric("Last Sale", str(last_sale))

        st.markdown("---")
        st.subheader("Revenue by Product")

        if not sales_df.empty:
            rev = sales_df.groupby("product")["amount"].sum().reset_index()
            st.dataframe(rev)

            chart = alt.Chart(rev).mark_bar().encode(
                x="amount:Q",
                y="product:N",
                tooltip=["product", "amount"]
            )
            st.altair_chart(chart, use_container_width=True)

        st.markdown("---")
        st.subheader("Revenue Over Time")

        if "date" in sales_df:
            df = sales_df.copy()
            df["date_only"] = df["date"].dt.date
            daily = df.groupby("date_only")["amount"].sum().reset_index()

            line = alt.Chart(daily).mark_line(point=True).encode(
                x="date_only:T",
                y="amount:Q"
            )
            st.altair_chart(line, use_container_width=True)

        st.subheader("Recent Sales")
        st.dataframe(sales_df.sort_values("date", ascending=False))

    # ------------------------------------------------
    # CUSTOMER DETAILS
    # ------------------------------------------------
    elif section == "👥 Customer Details":
        st.title("👥 Customer Details")

        col1, col2 = st.columns(2)

        total_customers = len(customers_df)

        if not customers_df.empty:
            newest = customers_df["joined_at"].max()
            newest_display = newest.strftime("%Y-%m-%d")
        else:
            newest_display = "—"

        col1.metric("Total Customers", total_customers)
        col2.metric("Newest Customer", newest_display)

        st.markdown("---")

        q = st.text_input("Search by name or email")
        filtered = customers_df

        if q:
            q_lower = q.lower()
            filtered = customers_df[
                customers_df["name"].str.lower().str.contains(q_lower)
                | customers_df["email"].str.lower().str.contains(q_lower)
            ]

        st.dataframe(filtered)

        st.markdown("---")
        st.subheader("New Customers Per Month")

        if not customers_df.empty:
            tmp = customers_df.copy()
            tmp["joined_month"] = tmp["joined_at"].dt.to_period("M").dt.to_timestamp()
            monthly = tmp.groupby("joined_month").size().reset_index(name="count")

            chart = alt.Chart(monthly).mark_bar().encode(
                x="joined_month:T",
                y="count:Q"
            )
            st.altair_chart(chart, use_container_width=True)

    # ------------------------------------------------
    # PRODUCT ANALYTICS
    # ------------------------------------------------
    elif section == "📦 Product Analytics":
        st.title("📦 Product Analytics")

        if not products_df.empty:
            st.dataframe(products_df)

            st.markdown("---")
            st.subheader("Low Stock Alerts")

            thresh = st.number_input("Low stock threshold", min_value=0, value=5)
            low = products_df[products_df["stock"] <= thresh]

            if not low.empty:
                st.warning(f"{len(low)} products low in stock")
                st.dataframe(low)
            else:
                st.success("All stock levels look good!")

            st.markdown("---")
            st.subheader("Inventory Value")

            products_df["inventory_value"] = products_df["price"] * products_df["stock"]
            total_value = products_df["inventory_value"].sum()

            st.metric("Total Inventory Value", f"₹ {total_value:,.0f}")
            st.dataframe(products_df)


# ------------------------------------------------
# APP ENTRY
# ------------------------------------------------
if "user" not in st.session_state:
    login_screen()
else:
    dashboard()

