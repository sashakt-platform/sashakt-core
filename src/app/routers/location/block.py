from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.location import Block

router = APIRouter()


# Create a Block
@router.post("/", response_model=Block)
def create_block(block: Block, session: Session = Depends(get_session)):
    session.add(block)
    session.commit()
    session.refresh(block)
    return block


# Get all Blocks
@router.get("/", response_model=list[Block])
def get_block(session: Session = Depends(get_session)):
    blocks = session.exec(select(Block)).all()
    return blocks


# Get Block by ID
@router.get("/{block_id}", response_model=Block)
def get_block_by_id(block_id: int, session: Session = Depends(get_session)):
    block = session.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return block


# Update a Block
@router.put("/{block_id}", response_model=Block)
def update_block(
    block_id: int, updated_data: Block, session: Session = Depends(get_session)
):
    block = session.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    block.name = updated_data.name
    session.add(block)
    session.commit()
    session.refresh(block)
    return block
