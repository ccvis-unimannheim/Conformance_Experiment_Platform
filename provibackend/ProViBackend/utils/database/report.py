import csv
from datetime import datetime
from ProViBackend.utils.database.connection import users_collection, questionnaire_collection, interaction_collection, prequestions_collection


def export_database_to_csv(output_file="report.csv"):
    try:
        # Fetch all users
        users = list(users_collection.find({}, {"_id": 0}))  # Exclude MongoDB _id field

        # Initialize CSV data structure
        csv_data = []

        # Iterate over users and gather related data
        for user in users:
            user_id = user["user_id"]

            # Get data from all tables
            prequestions = list(prequestions_collection.find({"user_id": user_id}, {"_id": 0}))
            questionnaires = list(questionnaire_collection.find({"user_id": user_id}, {"_id": 0}))
            interactions = list(interaction_collection.find({"user_id": user_id}, {"_id": 0}))

            # Combine all data for the user
            all_entries = (
                [{"type": "User", **user}] +
                [{"type": "PreQuestion", **entry} for entry in prequestions] +
                [{"type": "Questionnaire", **entry} for entry in questionnaires] +
                [{"type": "Interaction", **entry} for entry in interactions]
            )

            # Sort entries by timestamp (if available) or default to no timestamp
            sorted_entries = sorted(
                all_entries,
                key=lambda x: x.get("created_at", datetime.min)
            )

            # Add sorted entries to the CSV data
            csv_data.extend(sorted_entries)

        # Write to CSV file
        with open(output_file, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=csv_data[0].keys())
            writer.writeheader()
            writer.writerows(csv_data)

        print(f"Data exported successfully to {output_file}")

    except Exception as e:
        print("An error occurred:", e)
