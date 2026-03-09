#
#
#
# Database itself should not have concrete routes. Its just a helper function to connect to the database.
#
#
#
#
# from fastapi import APIRouter, HTTPException
# from ProViBackend.utils.database.connection import users_collection, questionnaire_collection, interaction_collection, prequestions_collection
#
# router = APIRouter()
#
# # Create a new user
# @router.post("/user")
# async def create_user(user: User):
#     if users_collection.find_one({"user_id": user.user_id}):
#         raise HTTPException(status_code=400, detail="User ID already exists.")
#
#     users_collection.insert_one(user.model_dump())
#     return {"message": "User created successfully"}
#
# # Create a new prequestion entry
# @router.post("/prequestion")
# async def create_interaction_entry(prequestion: PreQuestion):
#     if prequestions_collection.find_one({"interaction_id": prequestion.ui_id}):
#         raise HTTPException(status_code=400, detail="Prequestion ID already exists.")
#
#     prequestions_collection.insert_one(prequestion.model_dump())
#     return {"message": "Prequestion Entry created successfully"}
#
# # Create a new questionnaire entry
# @router.post("/questionnaire")
# async def create_questionnaire_entry(question: Questionnaire):
#     if questionnaire_collection.find_one({"user_id": question.question_id}):
#         raise HTTPException(status_code=400, detail="Question ID already exists.")
#
#     questionnaire_collection.insert_one(question.model_dump())
#     return {"message": "Questionnaire Entry created successfully"}
#
# # Create a new interaction entry
# @router.post("/interaction")
# async def create_interaction_entry(interaction: Interaction):
#     if interaction_collection.find_one({"interaction_id": interaction.ui_id}):
#         raise HTTPException(status_code=400, detail="Interaction ID already exists.")
#
#     interaction_collection.insert_one(interaction.model_dump())
#     return {"message": "Interaction Entry created successfully"}