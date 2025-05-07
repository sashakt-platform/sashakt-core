from sqlmodel import Session

from app.models import Tag, TagType
from app.tests.utils.organization import create_random_organization
from app.tests.utils.user import create_random_user
from app.tests.utils.utils import random_lower_string


def create_random_tag(session: Session) -> Tag:
    user = create_random_user(session)
    organization = create_random_organization(session)
    tag_type = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        organization_id=organization.id,
    )
    session.add(tag_type)
    session.commit()
    session.refresh(tag_type)

    tag = Tag(
        name=random_lower_string(),
        description=random_lower_string(),
        tag_type_id=tag_type.id,
        created_by_id=user.id,
        organization_id=organization.id,
    )
    session.add(tag)
    session.commit()
    session.refresh(tag)

    return tag
