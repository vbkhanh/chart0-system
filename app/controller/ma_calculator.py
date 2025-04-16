from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict
from datetime import datetime, timedelta, date
import numpy as np

from app.models.bar import Bar

async def line_segment_intersection(p1, q1, p2, q2):
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

async def find_discrete_intersections(line1, line2):
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
            intersection = await line_segment_intersection(p1, q1, p2, q2)
            if intersection:
                intersections.append(intersection)
    return intersections

async def calculate_ma_list_v2(session: AsyncSession, period: int, symbol_id: int, bar_type: str, start_date: date = None, end_date: date = None) -> List[Dict]:
    
    query = select(Bar).where(Bar.symbol_id == symbol_id).where(Bar.type == bar_type).order_by(Bar.from_time.desc())
    
    if start_date:
        query = query.where(Bar.from_time >= start_date)
    if end_date:
        query = query.where(Bar.from_time <= end_date)
    
    bars = await session.scalars(query)
    bars = bars.all()
    
    ma_list = []

    for index in range(len(bars) - period + 1):
        close_price_sum = sum([bar.close for bar in bars[index:index + period]])
        if len(bars[index:index + period]) < period:
            break
        ma_list.append({
            "date": bars[index].from_time,
            "value": close_price_sum / period
        })

    return ma_list

async def find_intersection(session: AsyncSession, ma1_list, ma2_list):
    # Convert date strings to numerical values and extract values
    def process_data(data):
        dates = [item["date"] for item in data]
        values = [item["value"] for item in data]
        numeric_dates = [(date - dates[0]).days for date in dates]  # Days since first date
        return list(zip(numeric_dates, values)), dates[0]
    
    # Convert x to datetime
    def convert_to_datetime(start_date, days):
        return start_date + timedelta(days=days)

    line1, start_date1 = process_data(ma1_list)
    line2, start_date2 = process_data(ma2_list)

    # Find intersections
    intersections = await find_discrete_intersections(line1, line2)

    # Print intersections
    result = []
    for point in intersections:
        intersection_date = convert_to_datetime(start_date1, point[0])
        x = intersection_date
        y = point[1]
        result.append([x, y])
    
    return result
