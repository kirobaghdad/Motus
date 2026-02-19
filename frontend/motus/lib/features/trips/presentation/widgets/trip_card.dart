import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class TripCard extends StatelessWidget {
  const TripCard({
    super.key,
    required this.tripDateTime,
    required this.startLocation,
    required this.destination,
    this.tripId,
  });

  final DateTime? tripDateTime;
  final String startLocation;
  final String destination;
  final String? tripId;

  @override
  Widget build(BuildContext context) {
    final formattedDate = tripDateTime != null
        ? DateFormat('MMM dd, yyyy').format(tripDateTime!)
        : '';
    final formattedTime = tripDateTime != null
        ? DateFormat('hh:mm a').format(tripDateTime!)
        : '';
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            (tripId != null)
                ? Text(
                    "Trip $tripId",
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  )
                : SizedBox(),
            const SizedBox(height: 10),
            Row(
              children: [
                Column(
                  children: [
                    Icon(Icons.navigation, color: Colors.green),
                    Container(width: 2, height: 30, color: Colors.grey),
                    Icon(Icons.location_on, color: Colors.red),
                  ],
                ),
                const SizedBox(width: 10),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      "from",
                      style: TextStyle(color: Colors.grey, fontSize: 12),
                    ),
                    Text(
                      startLocation,
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      "to",
                      style: TextStyle(color: Colors.grey, fontSize: 12),
                    ),
                    Text(
                      destination,
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                const Icon(Icons.calendar_today, size: 18),
                const SizedBox(width: 5),
                Text(formattedDate),
                const SizedBox(width: 20),
                const Icon(Icons.access_time, size: 18),
                const SizedBox(width: 5),
                Text(formattedTime),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
