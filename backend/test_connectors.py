import asyncio
from backend.connectors.ado import get_bugs_by_priority
from backend.connectors.graph import get_next_meetings
from backend.connectors.github import get_daily_commits
from backend.connectors.google import get_next_meetings as get_google_meetings

async def test_all():
    print("--- ADO ---")
    try:
        ado = await get_bugs_by_priority()
        print(f"Total bugs: {ado['total']}, By priority: {ado['by_priority']}")
        assert isinstance(ado['total'], int)
    except Exception as e:
        print(f"⚠️  ADO failed: {e}")

    print("\n--- GRAPH (Microsoft Calendar) ---")
    try:
        graph = await get_next_meetings(3)
        print(f"Meetings: {graph['count']}")
        for m in graph['meetings']:
            print(f"  {m['start']} - {m['title']}")
        assert isinstance(graph['count'], int)
    except Exception as e:
        print(f"⚠️  Graph failed: {e}")

    print("\n--- GOOGLE CALENDAR ---")
    try:
        google = await get_google_meetings(3)
        print(f"Events: {google['count']}")
        for m in google['meetings']:
            print(f"  {m['start']} - {m['subject']}")
        assert isinstance(google['count'], int)
    except Exception as e:
        print(f"⚠️  Google failed: {e}")

    print("\n--- GITHUB ---")
    try:
        gh = await get_daily_commits()
        print(f"Today's commits: {gh['total']}, Last: {gh['last_commit']}")
        assert isinstance(gh['total'], int)
    except Exception as e:
        print(f"⚠️  GitHub failed: {e}")

    print("\n✅ Connector tests complete!")

if __name__ == "__main__":
    asyncio.run(test_all())
