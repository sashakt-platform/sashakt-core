import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.core.db import engine
from app.core.provider_config import provider_config_service
from app.core.timezone import get_timezone_aware_now
from app.models import (
    Block,
    Candidate,
    CandidateTest,
    CandidateTestAnswer,
    District,
    Entity,
    EntityType,
    Organization,
    OrganizationProvider,
    Provider,
    Question,
    QuestionRevision,
    QuestionTag,
    State,
    Tag,
    TagType,
    Test,
    User,
)
from app.models.candidate import CandidateTestProfile
from app.models.provider import ProviderType
from app.models.test import TestDistrict, TestQuestion, TestTag
from app.models.user import UserState
from app.services.datasync.base import SyncResult
from app.services.datasync.bigquery import BigQueryService

logger = logging.getLogger(__name__)


class DataSyncService:
    """Direct BigQuery data synchronization service"""

    def get_organization_providers(
        self, organization_id: int
    ) -> list[OrganizationProvider]:
        with Session(engine) as session:
            statement = (
                select(OrganizationProvider)
                .join(Provider)
                .where(
                    OrganizationProvider.organization_id == organization_id,
                    OrganizationProvider.is_enabled,
                    Provider.is_active,
                )
                .options(selectinload(OrganizationProvider.provider))  # type: ignore[arg-type]
            )
            return list(session.exec(statement))

    def sync_organization_data(
        self, organization_id: int, incremental: bool = True
    ) -> dict[str, SyncResult]:
        """Synchronize organization data to BigQuery"""
        org_providers = self.get_organization_providers(organization_id)
        results: dict[str, SyncResult] = {}

        if not org_providers:
            return results

        # Determine actual sync mode
        actual_incremental = incremental
        logger.info(
            f"Initial sync mode for org {organization_id}: incremental={incremental}"
        )

        if incremental:
            # For incremental mode, check if dataset exists - if not, force full sync
            for org_provider in org_providers:
                if org_provider.provider.provider_type == ProviderType.BIGQUERY:
                    if org_provider.config_json is None:
                        continue
                    decrypted_config = provider_config_service.get_config_for_use(
                        org_provider.config_json
                    )
                    bigquery_service = BigQueryService(
                        organization_id, decrypted_config
                    )

                    if not bigquery_service.dataset_exists():
                        logger.info(
                            f"Dataset doesn't exist for org {organization_id}, forcing full sync"
                        )
                        actual_incremental = False
                    else:
                        logger.info(
                            f"Dataset exists for org {organization_id}, proceeding with incremental sync"
                        )
                    break
        else:
            # Full sync mode: always extract all data, ignore any existing sync metadata
            logger.info(
                f"Full sync mode for org {organization_id}, ignoring any existing sync metadata"
            )
            actual_incremental = False

        logger.info(
            f"Final sync mode for org {organization_id}: actual_incremental={actual_incremental}"
        )
        export_data = self._extract_organization_data(
            organization_id, actual_incremental
        )

        total_records = sum(len(records) for records in export_data.values())
        logger.info(
            f"Extracted {total_records} total records for org {organization_id}"
        )

        for org_provider in org_providers:
            # Only process BigQuery providers
            if org_provider.provider.provider_type != ProviderType.BIGQUERY:
                continue

            try:
                if org_provider.config_json is None:
                    continue
                decrypted_config = provider_config_service.get_config_for_use(
                    org_provider.config_json
                )

                bigquery_service = BigQueryService(organization_id, decrypted_config)

                if actual_incremental:
                    result = bigquery_service.execute_incremental_sync(
                        export_data, org_provider.last_sync_timestamp
                    )
                else:
                    result = bigquery_service.execute_full_sync(export_data)

                if result.success and org_provider.id is not None:
                    self._update_organization_provider_sync_timestamp(
                        org_provider.id, result.sync_timestamp
                    )

                results[f"{org_provider.provider.name}_{org_provider.id}"] = result

            except Exception as e:
                results[f"{org_provider.provider.name}_{org_provider.id}"] = SyncResult(
                    success=False,
                    records_exported=0,
                    tables_created=[],
                    tables_updated=[],
                    error_message=str(e),
                    sync_timestamp=get_timezone_aware_now(),
                )

        return results

    def sync_all_organizations_data(
        self, incremental: bool = True
    ) -> dict[int, dict[str, SyncResult]]:
        """Synchronize data for all active organizations"""
        results: dict[int, dict[str, SyncResult]] = {}

        with Session(engine) as session:
            organizations = session.exec(
                select(Organization).where(
                    Organization.is_active,
                    ~Organization.is_deleted,  # type: ignore[arg-type]
                )
            ).all()

            for org in organizations:
                if org.id is None:
                    continue
                try:
                    org_results = self.sync_organization_data(org.id, incremental)
                    if org_results:
                        results[org.id] = org_results
                except Exception as e:
                    results[org.id] = {
                        "error": SyncResult(
                            success=False,
                            records_exported=0,
                            tables_created=[],
                            tables_updated=[],
                            error_message=f"Organization sync failed: {str(e)}",
                            sync_timestamp=get_timezone_aware_now(),
                        )
                    }

        return results

    def _get_table_specific_last_sync(
        self, organization_id: int, table_name: str
    ) -> datetime | None:
        """Get the last sync timestamp for a specific table from BigQuery metadata"""
        try:
            # Get the organization provider to access BigQuery
            org_providers = self.get_organization_providers(organization_id)
            if not org_providers:
                return None

            # Use the first BigQuery provider (assuming one per org)
            for org_provider in org_providers:
                if org_provider.provider.provider_type == ProviderType.BIGQUERY:
                    if org_provider.config_json is None:
                        continue
                    decrypted_config = provider_config_service.get_config_for_use(
                        org_provider.config_json
                    )
                    bigquery_service = BigQueryService(
                        organization_id, decrypted_config
                    )

                    # Get table-specific sync metadata
                    last_sync_timestamp, _ = bigquery_service.get_table_sync_metadata(
                        table_name
                    )
                    return last_sync_timestamp

            return None
        except Exception:
            # If we can't get table-specific timestamp, return None to do full sync
            return None

    def test_provider_connection(self, organization_id: int, provider_id: int) -> bool:
        """Test connection to a BigQuery provider"""
        with Session(engine) as session:
            org_provider = session.exec(
                select(OrganizationProvider)
                .join(Provider)
                .where(
                    OrganizationProvider.organization_id == organization_id,
                    OrganizationProvider.provider_id == provider_id,
                )
                .options(selectinload(OrganizationProvider.provider))  # type: ignore[arg-type]
            ).first()

            if not org_provider:
                return False

            # Only test BigQuery connections
            if org_provider.provider.provider_type != ProviderType.BIGQUERY:
                return False

            try:
                if org_provider.config_json is None:
                    return False
                decrypted_config = provider_config_service.get_config_for_use(
                    org_provider.config_json
                )

                bigquery_service = BigQueryService(organization_id, decrypted_config)
                return bigquery_service.test_connection()
            except Exception:
                return False

    def _extract_organization_data(
        self, organization_id: int, incremental: bool = True
    ) -> dict[str, list[dict[str, Any]]]:
        data = {}

        with Session(engine) as session:
            # Use table-specific sync timestamps for all tables
            data["users"] = self._extract_users_data(
                session, organization_id, incremental
            )
            data["tests"] = self._extract_tests_data(
                session, organization_id, incremental
            )
            data["questions"] = self._extract_questions_data(
                session, organization_id, incremental
            )
            data["question_revisions"] = self._extract_question_revisions_data(
                session, organization_id, incremental
            )
            data["candidates"] = self._extract_candidates_data(
                session, organization_id, incremental
            )
            data["candidate_test_answers"] = self._extract_candidate_test_answers_data(
                session, organization_id, incremental
            )
            data["candidate_tests"] = self._extract_candidate_tests_data(
                session, organization_id, incremental
            )
            data["candidate_test_profiles"] = (
                self._extract_candidate_test_profiles_data(
                    session, organization_id, incremental
                )
            )
            data["states"] = self._extract_states_data(
                session, organization_id, incremental
            )
            data["districts"] = self._extract_districts_data(
                session, organization_id, incremental
            )
            data["blocks"] = self._extract_blocks_data(
                session, organization_id, incremental
            )
            data["entities"] = self._extract_entities_data(
                session, organization_id, incremental
            )
            data["entity_types"] = self._extract_entity_types_data(
                session, organization_id, incremental
            )
            data["tags"] = self._extract_tags_data(
                session, organization_id, incremental
            )
            data["tag_types"] = self._extract_tag_types_data(
                session, organization_id, incremental
            )
            data["question_tags"] = self._extract_question_tags_data(
                session, organization_id, incremental
            )
            data["test_questions"] = self._extract_test_questions_data(
                session, organization_id, incremental
            )
            data["test_tags"] = self._extract_test_tags_data(
                session, organization_id, incremental
            )
            data["test_districts"] = self._extract_test_districts_data(
                session, organization_id, incremental
            )
            data["user_states"] = self._extract_user_states_data(
                session, organization_id, incremental
            )

        return data

    def _extract_users_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        statement = select(User).where(User.organization_id == organization_id)

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "users"
            )
            if table_last_sync is not None:
                statement = statement.where(User.modified_date > table_last_sync)  # type: ignore[operator]  # type: ignore[operator]

        users = session.exec(statement).all()
        return [self._serialize_user(user) for user in users]

    def _extract_tests_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        statement = select(Test).where(Test.organization_id == organization_id)

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "tests"
            )
            if table_last_sync is not None:
                statement = statement.where(Test.modified_date > table_last_sync)  # type: ignore[operator]  # type: ignore[operator]

        tests = session.exec(statement).all()
        return [self._serialize_test(test) for test in tests]

    def _extract_questions_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        statement = select(Question).where(Question.organization_id == organization_id)

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "questions"
            )
            if table_last_sync is not None:
                statement = statement.where(Question.modified_date > table_last_sync)  # type: ignore[operator]  # type: ignore[operator]

        questions = session.exec(statement).all()
        return [self._serialize_question(question) for question in questions]

    def _extract_candidates_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        statement = select(Candidate).where(
            Candidate.organization_id == organization_id
        )

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "candidates"
            )
            if table_last_sync is not None:
                statement = statement.where(Candidate.modified_date > table_last_sync)  # type: ignore[operator]

        candidates = session.exec(statement).all()
        return [self._serialize_candidate(candidate) for candidate in candidates]

    def _extract_candidate_test_answers_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        # Filter candidate test answers by organization through candidate_test → test.organization_id
        statement = (
            select(CandidateTestAnswer, Test.organization_id)
            .join(
                CandidateTest,
                CandidateTestAnswer.candidate_test_id == CandidateTest.id,  # type: ignore[arg-type]
            )
            .join(Test, CandidateTest.test_id == Test.id)  # type: ignore[arg-type]
            .where(Test.organization_id == organization_id)
        )

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "candidate_test_answers"
            )
            if table_last_sync is not None:
                statement = statement.where(
                    CandidateTestAnswer.modified_date > table_last_sync  # type: ignore[operator]
                )

        results = session.exec(statement).all()
        return [
            self._serialize_candidate_test_answer(answer, org_id)
            for answer, org_id in results
        ]

    def _extract_candidate_tests_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        # Filter candidate tests by organization through test.organization_id
        statement = (
            select(CandidateTest, Test.organization_id)
            .join(Test, CandidateTest.test_id == Test.id)  # type: ignore[arg-type]
            .where(Test.organization_id == organization_id)
        )

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "candidate_tests"
            )
            if table_last_sync is not None:
                statement = statement.where(
                    CandidateTest.modified_date > table_last_sync  # type: ignore[operator]
                )

        results = session.exec(statement).all()
        return [
            self._serialize_candidate_test(candidate_test, org_id)
            for candidate_test, org_id in results
        ]

    def _extract_states_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        # States are shared across organizations, use table-specific sync timestamp
        statement = select(State).where(State.is_active)

        if incremental:
            # Get table-specific last sync timestamp from BigQuery metadata
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "states"
            )
            if table_last_sync is not None:
                statement = statement.where(State.modified_date > table_last_sync)  # type: ignore[operator]

        states = session.exec(statement).all()
        return [self._serialize_state(state) for state in states]

    def _extract_districts_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        # Districts are shared across organizations, use table-specific sync timestamp
        statement = select(District).where(District.is_active)

        if incremental:
            # Get table-specific last sync timestamp from BigQuery metadata
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "districts"
            )
            if table_last_sync is not None:
                statement = statement.where(District.modified_date > table_last_sync)  # type: ignore[operator]

        districts = session.exec(statement).all()
        return [self._serialize_district(district) for district in districts]

    def _extract_blocks_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        # Blocks are shared across organizations, use table-specific sync timestamp
        statement = select(Block).where(Block.is_active)

        if incremental:
            # Get table-specific last sync timestamp from BigQuery metadata
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "blocks"
            )
            if table_last_sync is not None:
                statement = statement.where(Block.modified_date > table_last_sync)  # type: ignore[operator]

        blocks = session.exec(statement).all()
        return [self._serialize_block(block) for block in blocks]

    def _extract_entities_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        # Filter entities by organization through entity_type relationship
        statement = (
            select(Entity)
            .join(EntityType, Entity.entity_type_id == EntityType.id)  # type: ignore[arg-type]
            .where(EntityType.organization_id == organization_id)
        )

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "entities"
            )
            if table_last_sync is not None:
                statement = statement.where(Entity.modified_date > table_last_sync)  # type: ignore[operator]

        entities = session.exec(statement).all()
        return [self._serialize_entity(entity) for entity in entities]

    def _extract_entity_types_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        statement = select(EntityType).where(
            EntityType.organization_id == organization_id
        )

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "entity_types"
            )
            if table_last_sync is not None:
                statement = statement.where(EntityType.modified_date > table_last_sync)  # type: ignore[operator]

        entity_types = session.exec(statement).all()
        return [self._serialize_entity_type(et) for et in entity_types]

    def _extract_tags_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        statement = select(Tag).where(Tag.organization_id == organization_id)

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "tags"
            )
            if table_last_sync is not None:
                statement = statement.where(Tag.modified_date > table_last_sync)  # type: ignore[operator]

        tags = session.exec(statement).all()
        return [self._serialize_tag(tag) for tag in tags]

    def _extract_tag_types_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        statement = select(TagType).where(TagType.organization_id == organization_id)

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "tag_types"
            )
            if table_last_sync is not None:
                statement = statement.where(TagType.modified_date > table_last_sync)  # type: ignore[operator]

        tag_types = session.exec(statement).all()
        return [self._serialize_tag_type(tag_type) for tag_type in tag_types]

    def _extract_question_tags_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        # Filter question_tags by organization through question relationship
        statement = (
            select(QuestionTag)
            .join(Question, QuestionTag.question_id == Question.id)  # type: ignore[arg-type]
            .where(Question.organization_id == organization_id)
        )

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "question_tags"
            )
            if table_last_sync is not None:
                statement = statement.where(QuestionTag.created_date > table_last_sync)  # type: ignore[operator]

        question_tags = session.exec(statement).all()
        return [self._serialize_question_tag(qt) for qt in question_tags]

    def _extract_question_revisions_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        # Filter question_revisions by organization through question relationship
        statement = (
            select(QuestionRevision)
            .join(Question, QuestionRevision.question_id == Question.id)  # type: ignore[arg-type]
            .where(Question.organization_id == organization_id)
        )

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "question_revisions"
            )
            if table_last_sync is not None:
                statement = statement.where(
                    QuestionRevision.modified_date > table_last_sync  # type: ignore[operator]
                )

        question_revisions = session.exec(statement).all()
        return [self._serialize_question_revision(qr) for qr in question_revisions]

    def _extract_candidate_test_profiles_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        # Filter candidate_test_profiles by organization through candidate_test → test.organization_id
        statement = (
            select(CandidateTestProfile, Test.organization_id)
            .join(
                CandidateTest,
                CandidateTestProfile.candidate_test_id == CandidateTest.id,  # type: ignore[arg-type]
            )
            .join(Test, CandidateTest.test_id == Test.id)  # type: ignore[arg-type]
            .where(Test.organization_id == organization_id)
        )

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "candidate_test_profiles"
            )
            if table_last_sync is not None:
                statement = statement.where(
                    CandidateTestProfile.created_date > table_last_sync  # type: ignore[operator]
                )

        results = session.exec(statement).all()
        return [
            self._serialize_candidate_test_profile(profile, org_id)
            for profile, org_id in results
        ]

    def _extract_test_questions_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        # Filter test_questions by organization through test.organization_id
        statement = (
            select(TestQuestion, Test.organization_id)
            .join(Test, TestQuestion.test_id == Test.id)  # type: ignore[arg-type]
            .where(Test.organization_id == organization_id)
        )

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "test_questions"
            )
            if table_last_sync is not None:
                statement = statement.where(TestQuestion.created_date > table_last_sync)  # type: ignore[operator]

        results = session.exec(statement).all()
        return [
            self._serialize_test_question(test_question, org_id)
            for test_question, org_id in results
        ]

    def _extract_test_tags_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        # Filter test_tags by organization through test.organization_id
        statement = (
            select(TestTag, Test.organization_id)
            .join(Test, TestTag.test_id == Test.id)  # type: ignore[arg-type]
            .where(Test.organization_id == organization_id)
        )

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "test_tags"
            )
            if table_last_sync is not None:
                statement = statement.where(TestTag.created_date > table_last_sync)  # type: ignore[operator]

        results = session.exec(statement).all()
        return [
            self._serialize_test_tag(test_tag, org_id) for test_tag, org_id in results
        ]

    def _extract_test_districts_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        # Filter test_districts through test.organization_id
        statement = (
            select(TestDistrict, Test.organization_id)
            .join(Test, TestDistrict.test_id == Test.id)  # type: ignore[arg-type]
            .where(Test.organization_id == organization_id)
        )

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "test_districts"
            )
            if table_last_sync is not None:
                statement = statement.where(TestDistrict.created_date > table_last_sync)  # type: ignore[operator]

        results = session.exec(statement).all()
        return [
            self._serialize_test_district(test_district, org_id)
            for test_district, org_id in results
        ]

    def _extract_user_states_data(
        self, session: Session, organization_id: int, incremental: bool
    ) -> list[dict[str, Any]]:
        # Filter user_states through user -> organization
        statement = (
            select(UserState)
            .join(User, UserState.user_id == User.id)  # type: ignore[arg-type]
            .where(User.organization_id == organization_id)
        )

        if incremental:
            table_last_sync = self._get_table_specific_last_sync(
                organization_id, "user_states"
            )
            if table_last_sync is not None:
                statement = statement.where(UserState.created_date > table_last_sync)  # type: ignore[operator]

        user_states = session.exec(statement).all()
        return [self._serialize_user_state(us) for us in user_states]

    def _serialize_user(self, user: User) -> dict[str, Any]:
        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "is_active": user.is_active,
            "role_id": user.role_id,
            "organization_id": user.organization_id,
            "created_date": (
                user.created_date.isoformat() if user.created_date else None
            ),
            "modified_date": (
                user.modified_date.isoformat() if user.modified_date else None
            ),
        }

    def _serialize_test(self, test: Test) -> dict[str, Any]:
        return {
            "id": test.id,
            "name": test.name,
            "description": test.description,
            "time_limit": test.time_limit,
            "is_active": test.is_active,
            "start_time": (test.start_time.isoformat() if test.start_time else None),
            "end_time": (test.end_time.isoformat() if test.end_time else None),
            "marks": test.marks,
            "created_by_id": test.created_by_id,
            "organization_id": test.organization_id,
            "created_date": (
                test.created_date.isoformat() if test.created_date else None
            ),
            "modified_date": (
                test.modified_date.isoformat() if test.modified_date else None
            ),
        }

    def _serialize_question(self, question: Question) -> dict[str, Any]:
        return {
            "id": question.id,
            "last_revision_id": question.last_revision_id,
            "is_active": question.is_active,
            "organization_id": question.organization_id,
            "created_date": (
                question.created_date.isoformat() if question.created_date else None
            ),
            "modified_date": (
                question.modified_date.isoformat() if question.modified_date else None
            ),
        }

    def _serialize_candidate(self, candidate: Candidate) -> dict[str, Any]:
        return {
            "id": candidate.id,
            "identity": candidate.identity,
            "user_id": candidate.user_id,
            "is_active": candidate.is_active,
            "organization_id": candidate.organization_id,
            "created_date": (
                candidate.created_date.isoformat() if candidate.created_date else None
            ),
            "modified_date": (
                candidate.modified_date.isoformat() if candidate.modified_date else None
            ),
        }

    def _serialize_candidate_test_answer(
        self, answer: CandidateTestAnswer, organization_id: int
    ) -> dict[str, Any]:
        return {
            "id": answer.id,
            "candidate_test_id": answer.candidate_test_id,
            "question_revision_id": answer.question_revision_id,
            "organization_id": organization_id,
            "response": answer.response,
            "time_spent": answer.time_spent,
            "visited": answer.visited,
            "created_date": (
                answer.created_date.isoformat() if answer.created_date else None
            ),
            "modified_date": (
                answer.modified_date.isoformat() if answer.modified_date else None
            ),
        }

    def _serialize_candidate_test(
        self, candidate_test: CandidateTest, organization_id: int
    ) -> dict[str, Any]:
        return {
            "id": candidate_test.id,
            "candidate_id": candidate_test.candidate_id,
            "test_id": candidate_test.test_id,
            "organization_id": organization_id,
            "start_time": (
                candidate_test.start_time.isoformat()
                if candidate_test.start_time
                else None
            ),
            "end_time": (
                candidate_test.end_time.isoformat() if candidate_test.end_time else None
            ),
            "is_submitted": candidate_test.is_submitted,
            "consent": candidate_test.consent,
            "device": candidate_test.device,
            "question_revision_ids": candidate_test.question_revision_ids,
            "created_date": (
                candidate_test.created_date.isoformat()
                if candidate_test.created_date
                else None
            ),
            "modified_date": (
                candidate_test.modified_date.isoformat()
                if candidate_test.modified_date
                else None
            ),
        }

    def _serialize_state(self, state: State) -> dict[str, Any]:
        return {
            "id": state.id,
            "name": state.name,
            "country_id": state.country_id,
            "is_active": state.is_active,
            "created_date": (
                state.created_date.isoformat() if state.created_date else None
            ),
            "modified_date": (
                state.modified_date.isoformat() if state.modified_date else None
            ),
        }

    def _serialize_district(self, district: District) -> dict[str, Any]:
        return {
            "id": district.id,
            "name": district.name,
            "state_id": district.state_id,
            "is_active": district.is_active,
            "created_date": (
                district.created_date.isoformat() if district.created_date else None
            ),
            "modified_date": (
                district.modified_date.isoformat() if district.modified_date else None
            ),
        }

    def _serialize_block(self, block: Block) -> dict[str, Any]:
        return {
            "id": block.id,
            "name": block.name,
            "district_id": block.district_id,
            "is_active": block.is_active,
            "created_date": (
                block.created_date.isoformat() if block.created_date else None
            ),
            "modified_date": (
                block.modified_date.isoformat() if block.modified_date else None
            ),
        }

    def _serialize_entity(self, entity: Entity) -> dict[str, Any]:
        return {
            "id": entity.id,
            "name": entity.name,
            "description": entity.description,
            "entity_type_id": entity.entity_type_id,
            "state_id": entity.state_id,
            "district_id": entity.district_id,
            "block_id": entity.block_id,
            "is_active": entity.is_active,
            "created_by_id": entity.created_by_id,
            "created_date": (
                entity.created_date.isoformat() if entity.created_date else None
            ),
            "modified_date": (
                entity.modified_date.isoformat() if entity.modified_date else None
            ),
        }

    def _serialize_entity_type(self, entity_type: EntityType) -> dict[str, Any]:
        return {
            "id": entity_type.id,
            "name": entity_type.name,
            "description": entity_type.description,
            "organization_id": entity_type.organization_id,
            "is_active": entity_type.is_active,
            "created_by_id": entity_type.created_by_id,
            "created_date": (
                entity_type.created_date.isoformat()
                if entity_type.created_date
                else None
            ),
            "modified_date": (
                entity_type.modified_date.isoformat()
                if entity_type.modified_date
                else None
            ),
        }

    def _serialize_tag(self, tag: Tag) -> dict[str, Any]:
        return {
            "id": tag.id,
            "name": tag.name,
            "description": tag.description,
            "tag_type_id": tag.tag_type_id,
            "organization_id": tag.organization_id,
            "is_active": tag.is_active,
            "created_by_id": tag.created_by_id,
            "created_date": (
                tag.created_date.isoformat() if tag.created_date else None
            ),
            "modified_date": (
                tag.modified_date.isoformat() if tag.modified_date else None
            ),
        }

    def _serialize_tag_type(self, tag_type: TagType) -> dict[str, Any]:
        return {
            "id": tag_type.id,
            "name": tag_type.name,
            "description": tag_type.description,
            "organization_id": tag_type.organization_id,
            "is_active": tag_type.is_active,
            "is_deleted": tag_type.is_deleted,
            "created_by_id": tag_type.created_by_id,
            "created_date": (
                tag_type.created_date.isoformat() if tag_type.created_date else None
            ),
            "modified_date": (
                tag_type.modified_date.isoformat() if tag_type.modified_date else None
            ),
        }

    def _serialize_question_tag(self, question_tag: QuestionTag) -> dict[str, Any]:
        return {
            "id": question_tag.id,
            "question_id": question_tag.question_id,
            "tag_id": question_tag.tag_id,
            "created_date": (
                question_tag.created_date.isoformat()
                if question_tag.created_date
                else None
            ),
        }

    def _serialize_question_revision(
        self, revision: QuestionRevision
    ) -> dict[str, Any]:
        return {
            "id": revision.id,
            "question_id": revision.question_id,
            "created_by_id": revision.created_by_id,
            "question_text": revision.question_text,
            "instructions": revision.instructions,
            "question_type": (
                revision.question_type.value if revision.question_type else None
            ),
            "options": revision.options,
            "correct_answer": revision.correct_answer,
            "subjective_answer_limit": revision.subjective_answer_limit,
            "is_mandatory": revision.is_mandatory,
            "is_active": revision.is_active,
            "marking_scheme": revision.marking_scheme,
            "solution": revision.solution,
            "media": revision.media,
            "is_deleted": revision.is_deleted,
            "created_date": (
                revision.created_date.isoformat() if revision.created_date else None
            ),
            "modified_date": (
                revision.modified_date.isoformat() if revision.modified_date else None
            ),
        }

    def _serialize_candidate_test_profile(
        self, profile: CandidateTestProfile, organization_id: int
    ) -> dict[str, Any]:
        return {
            "id": profile.id,
            "candidate_test_id": profile.candidate_test_id,
            "entity_id": profile.entity_id,
            "organization_id": organization_id,
            "created_date": (
                profile.created_date.isoformat() if profile.created_date else None
            ),
        }

    def _serialize_test_question(
        self, test_question: TestQuestion, organization_id: int
    ) -> dict[str, Any]:
        return {
            "id": test_question.id,
            "test_id": test_question.test_id,
            "question_revision_id": test_question.question_revision_id,
            "organization_id": organization_id,
            "created_date": (
                test_question.created_date.isoformat()
                if test_question.created_date
                else None
            ),
        }

    def _serialize_test_tag(
        self, test_tag: TestTag, organization_id: int
    ) -> dict[str, Any]:
        return {
            "id": test_tag.id,
            "test_id": test_tag.test_id,
            "tag_id": test_tag.tag_id,
            "organization_id": organization_id,
            "created_date": (
                test_tag.created_date.isoformat() if test_tag.created_date else None
            ),
        }

    def _serialize_test_district(
        self, test_district: TestDistrict, organization_id: int
    ) -> dict[str, Any]:
        return {
            "id": test_district.id,
            "test_id": test_district.test_id,
            "district_id": test_district.district_id,
            "organization_id": organization_id,
            "created_date": (
                test_district.created_date.isoformat()
                if test_district.created_date
                else None
            ),
        }

    def _serialize_user_state(self, user_state: UserState) -> dict[str, Any]:
        return {
            "id": user_state.id,
            "user_id": user_state.user_id,
            "state_id": user_state.state_id,
            "created_date": (
                user_state.created_date.isoformat() if user_state.created_date else None
            ),
        }

    def _get_last_organization_sync(self, organization_id: int) -> datetime | None:
        with Session(engine) as session:
            org_provider = session.exec(
                select(OrganizationProvider)
                .where(
                    OrganizationProvider.organization_id == organization_id,
                    OrganizationProvider.is_enabled,
                )
                .order_by(OrganizationProvider.last_sync_timestamp.desc())  # type: ignore[union-attr]
            ).first()

            return org_provider.last_sync_timestamp if org_provider else None

    def _update_organization_provider_sync_timestamp(
        self, org_provider_id: int, timestamp: datetime
    ) -> None:
        with Session(engine) as session:
            org_provider = session.get(OrganizationProvider, org_provider_id)
            if org_provider:
                org_provider.last_sync_timestamp = timestamp
                session.add(org_provider)
                session.commit()


data_sync_service = DataSyncService()
