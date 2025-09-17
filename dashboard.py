import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import json
from typing import Dict, Any, List
import numpy as np

# Page configuration
st.set_page_config(
    page_title="Webhook API Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    
    .metric-card {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .status-healthy {
        background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%);
    }
    
    .status-warning {
        background: linear-gradient(90deg, #f093fb 0%, #f5576c 100%);
    }
    
    .status-error {
        background: linear-gradient(90deg, #ff9a9e 0%, #fecfef 100%);
    }
    
    .sidebar-title {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

class WebhookMonitor:
    def __init__(self, api_base_url: str = "http://localhost:8443"):
        self.api_base_url = api_base_url
        self.session = requests.Session()
        self.session.timeout = 10
    
    def test_api_connection(self) -> Dict[str, Any]:
        """Test connection to webhook API"""
        try:
            response = self.session.get(f"{self.api_base_url}/health")
            if response.status_code == 200:
                return {"status": "healthy", "data": response.json()}
            else:
                return {"status": "error", "message": f"HTTP {response.status_code}"}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary from API"""
        try:
            response = self.session.get(f"{self.api_base_url}/api/metrics/summary")
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}"}
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def get_webhook_metrics(self, hours: int = 24, limit: int = 100) -> List[Dict]:
        """Get webhook metrics from API"""
        try:
            response = self.session.get(
                f"{self.api_base_url}/api/metrics/webhooks",
                params={"hours": hours, "limit": limit}
            )
            if response.status_code == 200:
                return response.json().get("metrics", [])
            else:
                return []
        except requests.exceptions.RequestException:
            return []
    
    def get_system_metrics(self, hours: int = 1) -> List[Dict]:
        """Get system metrics from API"""
        try:
            response = self.session.get(
                f"{self.api_base_url}/api/metrics/system",
                params={"hours": hours}
            )
            if response.status_code == 200:
                return response.json().get("metrics", [])
            else:
                return []
        except requests.exceptions.RequestException:
            return []
    
    def get_hourly_stats(self, hours: int = 24) -> Dict[str, Dict]:
        """Get hourly webhook statistics"""
        try:
            response = self.session.get(
                f"{self.api_base_url}/api/metrics/hourly",
                params={"hours": hours}
            )
            if response.status_code == 200:
                return response.json().get("hourly_stats", {})
            else:
                return {}
        except requests.exceptions.RequestException:
            return {}
    
    def get_webhook_file_analysis(self) -> Dict[str, Any]:
        """Get webhook file analysis"""
        try:
            response = self.session.get(f"{self.api_base_url}/api/analysis/webhook-files")
            if response.status_code == 200:
                return response.json().get("analysis", {})
            else:
                return {}
        except requests.exceptions.RequestException:
            return {}

def main():
    """Main dashboard function"""
    
    # Header
    st.markdown('<h1 class="main-header">🚀 Webhook API Monitoring Dashboard</h1>', unsafe_allow_html=True)
    
    # Sidebar configuration
    with st.sidebar:
        st.markdown('<div class="sidebar-title">⚙️ Configuration</div>', unsafe_allow_html=True)
        
        api_url = st.text_input(
            "API URL",
            value="http://localhost:8443",
            help="Base URL của Webhook API"
        )
        
        auto_refresh = st.checkbox("Auto Refresh", value=True)
        refresh_interval = st.selectbox(
            "Refresh Interval (seconds)",
            [5, 10, 30, 60],
            index=1
        )
        
        time_range = st.selectbox(
            "Time Range",
            ["1 hour", "6 hours", "24 hours", "7 days"],
            index=2
        )
        
        # Convert time range to hours
        time_range_hours = {
            "1 hour": 1,
            "6 hours": 6, 
            "24 hours": 24,
            "7 days": 168
        }[time_range]
        
        st.markdown("---")
        st.markdown("### 📊 Dashboard Info")
        st.info("Real-time monitoring dashboard cho Webhook API trên Windows Server")
    
    # Initialize monitor
    monitor = WebhookMonitor(api_url)
    
    # Auto-refresh logic
    if auto_refresh:
        placeholder = st.empty()
        with placeholder.container():
            render_dashboard(monitor, time_range_hours)
        
        time.sleep(refresh_interval)
        st.rerun()
    else:
        render_dashboard(monitor, time_range_hours)

def render_dashboard(monitor: WebhookMonitor, time_range_hours: int):
    """Render the main dashboard"""
    
    # Test API connection
    connection_status = monitor.test_api_connection()
    
    # Connection status
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if connection_status["status"] == "healthy":
            st.success("✅ API Connection: Healthy")
        else:
            st.error(f"❌ API Connection Error: {connection_status.get('message', 'Unknown error')}")
            st.stop()
    
    # Get data
    summary = monitor.get_metrics_summary()
    webhook_metrics = monitor.get_webhook_metrics(hours=time_range_hours)
    system_metrics = monitor.get_system_metrics(hours=min(time_range_hours, 24))
    hourly_stats = monitor.get_hourly_stats(hours=time_range_hours)
    file_analysis = monitor.get_webhook_file_analysis()
    
    # Main metrics row
    if summary and "webhook" in summary:
        webhook_data = summary["webhook"]
        system_data = summary.get("system", {})
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Requests (24h)",
                webhook_data.get("total_requests", 0),
                delta=None
            )
        
        with col2:
            success_rate = webhook_data.get("success_rate", 0)
            st.metric(
                "Success Rate",
                f"{success_rate}%",
                delta=f"{success_rate - 95:.1f}%" if success_rate > 0 else None
            )
        
        with col3:
            avg_time = webhook_data.get("avg_process_time", 0)
            st.metric(
                "Avg Response Time",
                f"{avg_time:.3f}s",
                delta=f"{avg_time - 0.1:.3f}s" if avg_time > 0 else None
            )
        
        with col4:
            total_transactions = webhook_data.get("total_transactions", 0)
            st.metric(
                "Total Transactions",
                total_transactions,
                delta=None
            )
    
    st.markdown("---")
    
    # Charts row 1
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Request Volume Over Time")
        if hourly_stats:
            df_hourly = pd.DataFrame([
                {
                    "hour": hour,
                    "total": stats["total"],
                    "success": stats["success"],
                    "failed": stats["failed"]
                }
                for hour, stats in hourly_stats.items()
            ]).sort_values("hour")
            
            if not df_hourly.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_hourly["hour"],
                    y=df_hourly["total"],
                    mode="lines+markers",
                    name="Total Requests",
                    line=dict(color="#1f77b4", width=3)
                ))
                fig.add_trace(go.Scatter(
                    x=df_hourly["hour"],
                    y=df_hourly["success"],
                    mode="lines+markers",
                    name="Successful",
                    line=dict(color="#2ca02c", width=2)
                ))
                fig.add_trace(go.Scatter(
                    x=df_hourly["hour"],
                    y=df_hourly["failed"],
                    mode="lines+markers",
                    name="Failed",
                    line=dict(color="#d62728", width=2)
                ))
                
                fig.update_layout(
                    xaxis_title="Hour",
                    yaxis_title="Requests",
                    hovermode="x unified",
                    template="plotly_white"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hourly data available")
        else:
            st.info("No data available")
    
    with col2:
        st.subheader("💾 System Resources")
        if system_metrics:
            df_system = pd.DataFrame(system_metrics)
            if not df_system.empty:
                df_system["timestamp"] = pd.to_datetime(df_system["timestamp"])
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_system["timestamp"],
                    y=df_system["cpu_percent"],
                    mode="lines",
                    name="CPU %",
                    line=dict(color="#ff7f0e")
                ))
                fig.add_trace(go.Scatter(
                    x=df_system["timestamp"],
                    y=df_system["memory_percent"],
                    mode="lines",
                    name="Memory %",
                    line=dict(color="#2ca02c")
                ))
                fig.add_trace(go.Scatter(
                    x=df_system["timestamp"],
                    y=df_system["disk_usage_percent"],
                    mode="lines",
                    name="Disk %",
                    line=dict(color="#d62728")
                ))
                
                fig.update_layout(
                    xaxis_title="Time",
                    yaxis_title="Usage %",
                    yaxis=dict(range=[0, 100]),
                    hovermode="x unified",
                    template="plotly_white"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No system data available")
        else:
            st.info("No system metrics available")
    
    st.markdown("---")
    
    # Charts row 2  
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⚡ Response Time Distribution")
        if webhook_metrics:
            df_webhooks = pd.DataFrame(webhook_metrics)
            if not df_webhooks.empty and "process_time" in df_webhooks.columns:
                fig = px.histogram(
                    df_webhooks,
                    x="process_time",
                    nbins=30,
                    title="Response Time Distribution",
                    labels={"process_time": "Response Time (s)", "count": "Frequency"},
                    color_discrete_sequence=["#1f77b4"]
                )
                fig.update_layout(template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No response time data available")
        else:
            st.info("No webhook data available")
    
    with col2:
        st.subheader("🏦 Transaction Analysis")
        if file_analysis and file_analysis.get("transactions_by_type"):
            tx_types = file_analysis["transactions_by_type"]
            
            fig = go.Figure(data=[go.Pie(
                labels=list(tx_types.keys()),
                values=list(tx_types.values()),
                hole=0.4,
                marker_colors=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
            )])
            
            fig.update_layout(
                title="Transaction Types",
                template="plotly_white",
                showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No transaction analysis data available")
    
    st.markdown("---")
    
    # Recent webhooks table
    st.subheader("📋 Recent Webhook Events")
    if webhook_metrics:
        df_recent = pd.DataFrame(webhook_metrics[:20])  # Show last 20
        if not df_recent.empty:
            # Format the DataFrame for display
            display_df = df_recent[[
                "timestamp", "batch_id", "source_app_id", 
                "transaction_count", "processed_count", "failed_count",
                "process_time", "status_code", "client_ip"
            ]].copy()
            
            # Format timestamp
            display_df["timestamp"] = pd.to_datetime(display_df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            display_df["process_time"] = display_df["process_time"].round(3)
            
            # Add status column with colors
            display_df["status"] = display_df.apply(
                lambda row: "✅ Success" if row["status_code"] == 200 and row["failed_count"] == 0 
                else "⚠️ Partial" if row["status_code"] == 200 and row["failed_count"] > 0
                else "❌ Failed",
                axis=1
            )
            
            st.dataframe(
                display_df,
                use_container_width=True,
                height=400
            )
        else:
            st.info("No recent webhook data available")
    else:
        st.info("No webhook data available")
    
    # Footer with last update time
    st.markdown("---")
    st.markdown(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Debug info (collapsible)
    with st.expander("🔍 Debug Information"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.json(summary, expanded=False)
        
        with col2:
            if file_analysis:
                st.json(file_analysis, expanded=False)


if __name__ == "__main__":
    main()