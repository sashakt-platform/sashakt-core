from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.location import Block, BlockCreate, BlockPublic, BlockUpdate

router = APIRouter()


# Create a Block
@router.post("/", response_model=BlockPublic)
def create_block(
    *,
    block_create: BlockCreate,
    session: Session = Depends(get_session),
) -> Any:
    block = Block.model_validate(block_create)
    session.add(block)
    session.commit()
    session.refresh(block)
    return block


# Get all Blocks
@router.get("/", response_model=list[BlockPublic])
def get_block(session: Session = Depends(get_session)):
    blocks = session.exec(select(Block)).all()
    return blocks


# Get Block by ID
@router.get("/{block_id}", response_model=BlockPublic)
def get_block_by_id(block_id: int, session: Session = Depends(get_session)):
    block = session.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return block


# Update Block by ID
@router.put("/{block_id}", response_model=BlockPublic)
def update_block(
    *,
    block_id: int,
    block_update: BlockUpdate,
    session: Session = Depends(get_session),
) -> Any:
    block_db = session.get(Block, block_id)
    if not block_db:
        raise HTTPException(status_code=404, detail="Block not found")
    block_data = block_update.model_dump(exclude_unset=True)
    block_db.sqlmodel_update(block_data)
    session.add(block_db)
    session.commit()
    session.refresh(block_db)
    return block_db
