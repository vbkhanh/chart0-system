import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def line_segment_intersection(p1, q1, p2, q2):
    """
    Find the intersection point of two line segments (p1, q1) and (p2, q2).

    Parameters:
    p1, q1: Endpoints of the first line segment (tuple of x, y).
    p2, q2: Endpoints of the second line segment (tuple of x, y).

    Returns:
    (x, y): The intersection point as a tuple if it exists, else None.
    """
    def orientation(p, q, r):
        """Determine the orientation of the triplet (p, q, r)."""
        val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
        if val == 0:
            return 0  # Collinear
        return 1 if val > 0 else 2  # Clockwise or counterclockwise

    def on_segment(p, q, r):
        """Check if point q lies on segment pr."""
        return (min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and
                min(p[1], r[1]) <= q[1] <= max(p[1], r[1]))

    o1 = orientation(p1, q1, p2)
    o2 = orientation(p1, q1, q2)
    o3 = orientation(p2, q2, p1)
    o4 = orientation(p2, q2, q1)

    if o1 != o2 and o3 != o4:
        # Compute intersection point
        A1 = q1[1] - p1[1]
        B1 = p1[0] - q1[0]
        C1 = A1 * p1[0] + B1 * p1[1]

        A2 = q2[1] - p2[1]
        B2 = p2[0] - q2[0]
        C2 = A2 * p2[0] + B2 * p2[1]

        det = A1 * B2 - A2 * B1
        if det == 0:
            return None  # Lines are parallel

        x = (B2 * C1 - B1 * C2) / det
        y = (A1 * C2 - A2 * C1) / det
        return (x, y)

    if o1 == 0 and on_segment(p1, p2, q1): return p2
    if o2 == 0 and on_segment(p1, q2, q1): return q2
    if o3 == 0 and on_segment(p2, p1, q2): return p1
    if o4 == 0 and on_segment(p2, q1, q2): return q1

    return None

def find_discrete_intersections(line1, line2):
    """
    Find intersections between two discrete polyline paths.

    Parameters:
    line1: List of points (x, y) representing the first line.
    line2: List of points (x, y) representing the second line.

    Returns:
    intersections: List of (x, y) tuples where the lines intersect.
    """
    intersections = []
    for i in range(len(line1) - 1):
        for j in range(len(line2) - 1):
            p1, q1 = line1[i], line1[i + 1]
            p2, q2 = line2[j], line2[j + 1]
            intersection = line_segment_intersection(p1, q1, p2, q2)
            if intersection:
                intersections.append(intersection)
    return intersections

# Example usage
if __name__ == "__main__":
    # Import data for MA5 and MA10
    from coordinates import MA5, MA10

    # Convert date strings to numerical values and extract values
    def process_data(data):
        dates = [datetime.strptime(item["date"], "%Y-%m-%d") for item in data]
        values = [item["value"] for item in data]
        numeric_dates = [(date - dates[0]).days for date in dates]  # Days since first date
        return list(zip(numeric_dates, values)), dates[0]

    line1, start_date1 = process_data(MA5)
    line2, start_date2 = process_data(MA10)

    # Find intersections
    intersections = find_discrete_intersections(line1, line2)

    # Convert x to datetime
    def convert_to_datetime(start_date, days):
        return start_date + timedelta(days=days)

    # Print intersections
    print("Intersections:")
    for point in intersections:
        intersection_date = convert_to_datetime(start_date1, point[0])
        print(f"x = {intersection_date.strftime('%Y-%m-%d')}, y = {point[1]:.3f}")

    # Plot the lines and their intersections
    line1_x, line1_y = zip(*line1)
    line2_x, line2_y = zip(*line2)

    plt.plot(line1_x, line1_y, label="MA5", marker='o')
    plt.plot(line2_x, line2_y, label="MA10", marker='o')

    for (x, y) in intersections:
        plt.plot(x, y, 'ro')  # Mark intersections

    plt.legend()
    plt.xlabel("Days since start")
    plt.ylabel("Value")
    plt.title("Intersection of MA5 and MA10")
    plt.grid()
    plt.show()
