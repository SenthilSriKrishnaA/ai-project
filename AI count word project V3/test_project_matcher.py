from project_matcher import find_similar_projects


idea = """
AI based healthcare chatbot using RAG.
The system uses large language models to answer
medical questions from trusted documents.
"""


results = find_similar_projects(idea)


print("\nRepository projects checked:")
print(results["total_projects"])


print("\nMeaningful matches:")

if not results["results"]:
    print("No highly similar project was found in the available repository.")

else:
    for result in results["results"]:
        print(
            f"{result['filename']} | "
            f"{result['score']}% | "
            f"{result['classification']}"
        )