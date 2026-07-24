import argparse
import json

# Simulate traffic flow based on given parameters
def simulate_traffic(params):
    num_vehicles = params.get("num_vehicles", 100)
    signal_timing = params.get("signal_timing", 30)  # in seconds
    max_speed = params.get("max_speed", 50)  # in km/h
    road_length = params.get("road_length", 5)  # in kilometers

    # Convert max_speed to m/s for calculations
    max_speed_mps = max_speed * 1000 / 3600

    # Calculate traffic density (vehicles per km)
    traffic_density = num_vehicles / road_length

    # Define road capacity (vehicles per km for free flow)
    road_capacity = 40  # Typical value for a single-lane road

    # Calculate flow rate (vehicles per second)
    if traffic_density <= road_capacity:
        flow_rate = traffic_density * max_speed_mps / road_capacity
    else:
        # Congestion: flow rate decreases as density increases
        flow_rate = max_speed_mps * (1 - (traffic_density - road_capacity) / road_capacity)
        flow_rate = max(flow_rate, 0.1)  # Ensure a minimum flow rate

    # Calculate average travel time (seconds per vehicle)
    travel_time = road_length * 1000 / flow_rate  # Convert road length to meters

    # Adjust travel time based on signal timing
    signal_delay = (num_vehicles / road_capacity) * signal_timing * 0.5  # Half the vehicles stop at signals
    travel_time += signal_delay

    # Calculate CO2 emissions (kg per vehicle)
    base_emission_rate = 0.25  # kg CO2 per vehicle per km at optimal speed
    stop_and_go_penalty = 1 + (traffic_density / road_capacity) * 0.5
    co2_emissions = num_vehicles * base_emission_rate * road_length * stop_and_go_penalty

    # Calculate congestion level (0 to 1 scale)
    congestion_level = min(traffic_density / road_capacity, 1.0)

    return {
        "average_travel_time": travel_time / 60,  # Convert to minutes
        "co2_emissions": co2_emissions,
        "congestion_level": congestion_level
    }

if __name__ == "__main__":
    # Get parameters from command line arguments
    parser = argparse.ArgumentParser(description="Demo workflow using command placeholders from param domains")
    parser.add_argument("--max_speed", type=float, required=True)
    parser.add_argument("--num_vehicles", type=float, required=True)
    parser.add_argument("--signal_timing", type=float, required=True)
    parser.add_argument("--road_length", type=float, required=True)
    args = parser.parse_args()
    params = {
        "max_speed": args.max_speed,
        "num_vehicles": args.num_vehicles,
        "signal_timing": args.signal_timing,
        "road_length": args.road_length,
    }

    # Simulate traffic with the given parameters
    results = simulate_traffic(params)

    # Save results to a JSON file for Odatix to extract
    with open("workflow_results.json", "w") as f:
        json.dump(results, f, indent=4)

    print("Traffic simulation completed. Results saved to results.json.")

    with open("progress.txt", "w") as f:
        f.write("Progress: 100%")
