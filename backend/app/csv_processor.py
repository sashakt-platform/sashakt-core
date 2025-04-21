"""
CSV Data Processor

This script processes a CSV file with questions, options, and related metadata,
and creates the corresponding entities in the Sashakt backend via its API.

CSV Format:
    The CSV should have the following columns:
    - S No: Question number
    - State: Comma-separated list of states
    - Questions: The question text
    - Option A, Option B, Option C, Option D: The options
    - Correct Option: Which option is correct (A, B, C, D)
    - Training Tags: Comma-separated list of tags
"""

import argparse
import csv
from pathlib import Path
from typing import Any

import requests

try:
    from core.config import settings
except ImportError:

    class Settings:
        FIRST_SUPERUSER: str = "admin@example.com"
        FIRST_SUPERUSER_PASSWORD: str = "admin"

    settings = Settings()

API_BASE_URL = "http://localhost:8000/api/v1"
SUPERUSER = settings.FIRST_SUPERUSER
SUPERUSER_PASSWORD = settings.FIRST_SUPERUSER_PASSWORD


class SashaktDataProcessor:
    def __init__(self):
        self.token = self._get_authentication_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.organization_cache = {}
        self.state_cache = {}
        self.tag_type_cache = {}
        self.tag_cache = {}
        self.user_id = None

        self._get_current_user()

    def _get_authentication_token(self) -> str:
        """Get authentication token using environment variables"""
        login_data = {
            "username": SUPERUSER,
            "password": SUPERUSER_PASSWORD,
        }

        try:
            response = requests.post(
                f"{API_BASE_URL}/login/access-token", data=login_data
            )

            if response.status_code != 200:
                raise Exception(f"Failed to login: {response.text}")

            tokens = response.json()
            return str(tokens["access_token"])
        except Exception as e:
            raise Exception(f"Authentication failed: {str(e)}")

    def _get_current_user(self) -> None:
        """Get current user info and set user_id"""
        response = requests.get(f"{API_BASE_URL}/users/me", headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"Failed to get user info: {response.text}")
        self.user_id = response.json()["id"]
        print(f"Authenticated as user ID: {self.user_id}")

    def _create_or_get_organization(self, name: str) -> str:
        """Create organization if it doesn't exist, return organization ID"""
        if name in self.organization_cache:
            return str(self.organization_cache[name])

        # Check if organization exists
        response = requests.get(f"{API_BASE_URL}/organization/", headers=self.headers)
        if response.status_code == 200:
            organizations = response.json()
            for org in organizations:
                if org["name"] == name:
                    self.organization_cache[name] = org["id"]
                    return str(org["id"])

        # Create new organization
        response = requests.post(
            f"{API_BASE_URL}/organization/", json={"name": name}, headers=self.headers
        )

        if response.status_code != 200:
            raise Exception(f"Failed to create organization: {response.text}")

        org_id = response.json()["id"]
        self.organization_cache[name] = org_id
        print(f"Created organization: {name} (ID: {org_id})")
        return str(org_id)

    def _create_or_get_states(self, state_names: list[str]) -> list[str]:
        """Create states if they don't exist, return list of state IDs"""
        state_ids = []

        for state_name in state_names:
            state_name = state_name.strip()
            if state_name in self.state_cache:
                state_ids.append(self.state_cache[state_name])
                continue

            # Check if state exists
            response = requests.get(
                f"{API_BASE_URL}/location/state/", headers=self.headers
            )
            if response.status_code == 200:
                states = response.json()
                state_found = False
                for state in states:
                    if state["name"] == state_name:
                        self.state_cache[state_name] = state["id"]
                        state_ids.append(state["id"])
                        state_found = True
                        break

                if state_found:
                    continue

            # Get India's country ID or create if needed
            country_id = self._create_or_get_country("India")

            # Create new state
            response = requests.post(
                f"{API_BASE_URL}/location/state/",
                json={"name": state_name, "country_id": country_id},
                headers=self.headers,
            )

            if response.status_code != 200:
                raise Exception(f"Failed to create state {state_name}: {response.text}")

            state_id = response.json()["id"]
            self.state_cache[state_name] = state_id
            state_ids.append(state_id)
            print(f"Created state: {state_name} (ID: {state_id})")

        return state_ids

    def _create_or_get_country(self, country_name: str) -> str:
        """Create country if it doesn't exist, return country ID"""
        # Check if country exists
        response = requests.get(
            f"{API_BASE_URL}/location/country/", headers=self.headers
        )
        if response.status_code == 200:
            countries = response.json()
            for country in countries:
                if country["name"] == country_name:
                    return str(country["id"])

        # Create new country
        response = requests.post(
            f"{API_BASE_URL}/location/country/",
            json={"name": country_name},
            headers=self.headers,
        )

        if response.status_code != 200:
            raise Exception(f"Failed to create country: {response.text}")

        country_id = response.json()["id"]
        print(f"Created country: {country_name} (ID: {country_id})")
        return str(country_id)

    def _create_or_get_tag_type(self, name: str, org_id: str) -> str:
        """Create tag type if it doesn't exist, return tag type ID"""
        cache_key = f"{name}_{org_id}"
        if cache_key in self.tag_type_cache:
            return str(self.tag_type_cache[cache_key])

        # Check if tag type exists
        response = requests.get(f"{API_BASE_URL}/tagtype/", headers=self.headers)
        if response.status_code == 200:
            tag_types = response.json()
            for tag_type in tag_types:
                if tag_type["name"] == name and tag_type["organization_id"] == org_id:
                    self.tag_type_cache[cache_key] = tag_type["id"]
                    return str(tag_type["id"])

        # Create new tag type
        response = requests.post(
            f"{API_BASE_URL}/tagtype/",
            json={
                "name": name,
                "description": f"Tag type for {name}",
                "created_by_id": self.user_id,
                "organization_id": org_id,
            },
            headers=self.headers,
        )

        if response.status_code != 200:
            raise Exception(f"Failed to create tag type: {response.text}")

        tag_type_id = response.json()["id"]
        self.tag_type_cache[cache_key] = tag_type_id
        print(f"Created tag type: {name} (ID: {tag_type_id})")
        return str(tag_type_id)

    def _create_or_get_tag(self, name: str, tag_type_id: str, org_id: str) -> str:
        """Create tag if it doesn't exist, return tag ID"""
        cache_key = f"{name}_{tag_type_id}_{org_id}"
        if cache_key in self.tag_cache:
            return str(self.tag_cache[cache_key])

        # Check if tag exists
        response = requests.get(f"{API_BASE_URL}/tag/", headers=self.headers)
        if response.status_code == 200:
            tags = response.json()
            for tag in tags:
                if tag["name"] == name and tag["tag_type_id"] == tag_type_id:
                    self.tag_cache[cache_key] = tag["id"]
                    return str(tag["id"])

        # Create new tag
        response = requests.post(
            f"{API_BASE_URL}/tag/",
            json={
                "name": name,
                "description": f"Tag for {name}",
                "tag_type_id": tag_type_id,
                "created_by_id": self.user_id,
                "organization_id": org_id,
            },
            headers=self.headers,
        )

        if response.status_code != 200:
            raise Exception(f"Failed to create tag: {response.text}")

        tag_id = response.json()["id"]
        self.tag_cache[cache_key] = tag_id
        print(f"Created tag: {name} (ID: {tag_id})")
        return str(tag_id)

    def _process_training_tags(self, tag_str: str, org_id: str) -> list[str]:
        """Process training tags string and create tags as needed"""
        if not tag_str:
            return []

        tag_ids = []
        # Split by comma if there are multiple tags
        tags = tag_str.split(",")

        for tag_text in tags:
            tag_text = tag_text.strip()
            tag_type_name = "Training Tag"
            tag_name = tag_text

            # Create the tag type if needed
            tag_type_id = self._create_or_get_tag_type(tag_type_name, org_id)

            # Create the tag linked to the tag type
            tag_id = self._create_or_get_tag(tag_name, tag_type_id, org_id)
            tag_ids.append(tag_id)

            print(f"Processed tag: {tag_type_name}:{tag_name}")

        return tag_ids

    def _create_question(
        self,
        question_text: str,
        options: list[str],
        correct_answer_index: str,
        org_id: str,
        tag_ids: list[str],
    ) -> str:
        """Create a question with options and correct answer"""
        # Convert option letter (A, B, C, D) to index (0, 1, 2, 3)
        letter_to_index = {"A": 0, "B": 1, "C": 2, "D": 3}
        correct_index = letter_to_index.get(correct_answer_index, 0)

        # Filter out empty options
        valid_options = []
        for _i, option in enumerate(options):
            if option.strip():
                valid_options.append({"text": option})

        question_data: dict[str, Any] = {
            "organization_id": org_id,
            "created_by_id": self.user_id,
            "question_text": question_text,
            "question_type": "single-choice",  # This should match QuestionType.single_choice in your backend
            "options": valid_options,
            "correct_answer": [correct_index],
            "is_mandatory": True,
            "tag_ids": tag_ids,
            "marking_scheme": {"correct": 1, "wrong": 0, "skipped": 0},
        }

        print(f"Creating question with data: {question_data}")

        response = requests.post(
            f"{API_BASE_URL}/questions/", json=question_data, headers=self.headers
        )

        if response.status_code != 200:
            raise Exception(f"Failed to create question: {response.text}")

        question_data = response.json()
        question_id = question_data["id"]
        revision_id = self._get_current_revision_id(
            str(question_id)
        )  # Get revision ID for test creation

        print(
            f"Created question: {question_text[:30]}... (ID: {question_id}, Revision: {revision_id})"
        )

        return str(revision_id)

    def _get_current_revision_id(self, question_id: str) -> str:
        try:
            response = requests.get(
                f"{API_BASE_URL}/questions/{question_id}/revisions",
                headers=self.headers,
            )

            if response.status_code == 200:
                revisions = response.json()
                for rev in revisions:
                    if rev.get("is_current", False):
                        return str(rev["id"])

                # If no current revision found, but we have revisions, use the first one
                if revisions:
                    return str(revisions[0]["id"])

            print(f"Warning: Could not get revision ID for question {question_id}")
            return str(question_id)
        except Exception as e:
            print(f"Error getting revision ID: {str(e)}")
            return str(question_id)

    def _create_test(
        self,
        name: str,
        description: str,
        question_revision_ids: list[str],
        tag_ids: list[str],
        state_ids: list[str],
        org_id: str,
    ) -> str:
        """Create a test with questions, tags and states"""
        test_data: dict[str, Any] = {
            "name": name,
            "description": description,
            "link": "https://veddis.org/",
            "time_limit": 10,
            "completion_message": "Test completed successfully",
            "start_instructions": "Read all questions carefully",
            "no_of_attempts": 1,
            "shuffle": False,
            "random_questions": False,
            "no_of_questions": len(question_revision_ids),
            "question_pagination": 1,
            "is_template": False,
            "organization_id": org_id,
            "created_by_id": self.user_id,
            "question_revision_ids": question_revision_ids,
            "tags": tag_ids,
            "states": state_ids,
        }

        response = requests.post(
            f"{API_BASE_URL}/test/", json=test_data, headers=self.headers
        )

        if response.status_code != 200:
            raise Exception(f"Failed to create test: {response.text}")

        test_id = response.json()["id"]
        print(f"Created test: {name} (ID: {test_id})")
        return str(test_id)

    def process_csv(self, csv_path: str, organization_name: str = "Sashakt") -> None:
        """Process CSV file and create entities in Sashakt backend"""
        org_id = self._create_or_get_organization(organization_name)

        question_ids = []
        all_tag_ids = set()
        all_state_ids = set()

        with open(csv_path, encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Skip rows without question text
                if not row.get("Questions", "").strip():
                    continue

                # Extract data from row
                states_str = row.get("State", "")
                question_text = row.get("Questions", "")
                option_a = row.get("Option A", "")
                option_b = row.get("Option B", "")
                option_c = row.get("Option C", "")
                option_d = row.get("Option D", "")
                correct_option = row.get("Correct Option", "A")
                training_tags_str = row.get("Training Tags", "")

                # Process states
                if states_str:
                    # Handle states that may be separated by commas or other delimiters
                    state_names = [
                        s.strip()
                        for s in states_str.replace(", ", ",").split(",")
                        if s.strip()
                    ]
                    state_ids = self._create_or_get_states(state_names)
                    all_state_ids.update(state_ids)
                    print(f"Processed states: {state_names}")

                # Process tags
                tag_ids = self._process_training_tags(training_tags_str, org_id)
                all_tag_ids.update(tag_ids)

                # Create question
                options = [option_a, option_b, option_c, option_d]
                revision_id = self._create_question(
                    question_text=question_text,
                    options=options,
                    correct_answer_index=correct_option,
                    org_id=org_id,
                    tag_ids=tag_ids,
                )
                question_ids.append(revision_id)

                # break

        if question_ids:
            # Create a test with all questions, tags and states
            test_name = Path(csv_path).stem
            self._create_test(
                name=f"Test from {test_name}",
                description=f"Automatically generated test from {csv_path}",
                question_revision_ids=question_ids,
                tag_ids=list(all_tag_ids),
                state_ids=list(all_state_ids),
                org_id=org_id,
            )

            print(
                f"Successfully processed {len(question_ids)} questions from {csv_path}"
            )
        else:
            print("No valid questions found in the CSV file.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process CSV and create entities in Sashakt backend"
    )
    parser.add_argument("csv_path", help="Path to the CSV file")

    args = parser.parse_args()

    print(f"Processing CSV file: {args.csv_path}")

    try:
        processor = SashaktDataProcessor()
        processor.process_csv(args.csv_path, organization_name="Veddis")
        print("\n✅ CSV processing completed successfully!")
    except Exception as e:
        print(f"\n❌ Error processing CSV: {str(e)}")
        import traceback

        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
