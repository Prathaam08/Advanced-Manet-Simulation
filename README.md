# 🌐 MANET Protocol Auto-Tester
**Advanced Mobile Ad-hoc Network Protocol Testing & Analysis Tool**

The **MANET Protocol Auto-Tester** is a web-based simulation tool designed for students, researchers, and network enthusiasts to visualize and compare the performance of various Mobile Ad-hoc Network (MANET) routing protocols. It provides an intuitive interface to configure network scenarios, run automated tests, and analyze results through a comprehensive report.

---

## ✨ Key Features
- **Interactive Visualization**: Real-time canvas displays the network topology, node movements, and active communication links.  
- **Flexible Configuration**: Easily set up network parameters such as number of nodes, simulation area, transmission range, and node mobility models.  
- **Automated Multi-Protocol Testing**: Select and automatically test multiple MANET protocols (AODV, DSDV, DSR, OLSR) under the same conditions for direct comparison.  
- **Customizable Scenarios**: Run multiple test scenarios with varying random seeds or define specific source-destination pairs for targeted analysis.  
- **Live Performance Metrics**: View key metrics like the best-performing protocol and packet delivery rate in real-time as the simulation progresses.  
- **Detailed Reporting**: Generate a comprehensive final report that summarizes the performance of each protocol across all test scenarios, highlighting key metrics like:  
  - 📦 Packet Delivery Ratio (PDR)  
  - ⏱️ Average End-to-End Delay  
  - 📊 Routing Overhead  
- **Hybrid Architecture**:  
  - **Python Backend (Flask + Socket.IO)** → Handles protocol simulation, metrics calculation, and data streaming.  
  - **JavaScript Frontend (HTML5 + CSS3)** → Handles visualization, animations, and report display.  

---

## 🛠️ Technologies Used
- **Frontend**  
  - HTML5 → Interface structure  
  - CSS3 → Styling and responsiveness  
  - JavaScript (ES6+) → Visualization, animations, data updates  

- **Backend**  
  - Python 3.x  
  - Flask (for web server & REST endpoints)  
  - Flask-SocketIO (real-time communication with frontend)  
  - Simulation Engine (custom Python logic for mobility models, routing protocols, metrics)   

---

## 🚀 How to Run
No installation is needed. Simply download the project files and open the `index.html` file in your preferred web browser.

1. Clone or download the repository.  
2. Navigate to the project directory.  
3. run python app.py 

---

## ⚙️ How to Use the Tester

### 🔧 Network Configuration
- **Number of Nodes**: Set the total number of mobile nodes in the network.  
- **Area Width/Height**: Define the dimensions of the simulation area in meters.  
- **Transmission Range**: Specify the maximum communication range for each node.  

### 🧪 Test Configuration
- **Number of Test Scenarios**: Define how many times the simulation will run (with different random seeds) to average the results.  
- **Simulation Time**: Set the duration for each individual scenario in seconds.  
- **Mobility Model**: Choose how the nodes move (Random Waypoint or Static).  
- **Packet Generation Rate**: Set the frequency of data packet creation.  

### 🎯 Route Selection (Optional)
- By default, the simulation uses random source and destination nodes for each run.  
- Check **"Enable Source & Destination Selection"** to test a specific communication path.  
- Select the desired nodes from the dropdowns.  

### 📡 Protocol Selection
- Check the boxes for the routing protocols you wish to test and compare (e.g., AODV, DSDV, DSR, OLSR).  

### ▶️ Start the Test
1. Click the **🚀 Start Auto Test** button.  
2. Observe node movements and network activity on the canvas.  
3. Monitor the live progress and results in the stats panel.  

### 📊 View the Report
- Once the simulation is complete, a **"Simulation Complete!"** alert will appear.  
- Click the **📊 View Report** button to open a detailed modal comparing the performance of all tested protocols.  

---

