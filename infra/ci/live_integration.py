"""Manual live checks. Print only status, never credentials or provider bodies."""
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def require(name):
    if not os.getenv(name, '').strip():
        raise RuntimeError(f'Missing integration secret: {name}')


def kure():
    # A child process prevents the two services' app packages from colliding.
    code = '''
import tempfile
from pathlib import Path
from langchain_core.documents import Document
from rag.retrieval import faiss_store
with tempfile.TemporaryDirectory() as folder:
    faiss_store.FAISS_DIR = Path(folder)
    docs = [Document(page_content='청년 월세 주거 지원', metadata={'source_key':'housing'}),
            Document(page_content='청년 직업훈련 취업 지원', metadata={'source_key':'jobs'})]
    faiss_store.replace_documents(docs, 'web', sources={'housing','jobs'})
    store = faiss_store.load_vectorstore('web')
    assert store.similarity_search('청년 월세 주거 지원', k=1)[0].metadata['source_key']=='housing'
print('PASS: real KURE embedding, FAISS persistence and retrieval')
'''
    subprocess.run([sys.executable, '-c', code], cwd=ROOT/'services/fastapi', check=True)


async def providers(target):
    sys.path.insert(0, str(ROOT/'services/fastapi'))
    from app.agents.policy_agent import GraphPolicyAgent
    from app.graph.nodes import LLMReasoner
    from app.graph.state import RAGRequest, UserProfile
    from app.graph.workflow import PolicyRagService
    keyword = os.getenv('POLICY_KEYWORD', '월세').strip()
    if target in {'policy', 'all'}:
        require('YOUTH_POLICY_API_KEY')
        agent = GraphPolicyAgent()
        result = await agent.lookup(keyword, ['지원 내용'])
        if result.status != 'used' or not result.documents:
            raise RuntimeError('Policy API did not return usable records for the selected keyword')
        policy_no = result.documents[0].metadata['policy_id']
        if not policy_no:
            raise RuntimeError('Policy API result has no policy identifier')
        detail = await agent.agent.get_detail(policy_no)
        if not detail['policies']:
            raise RuntimeError('Policy detail lookup returned no records')
        print('PASS: real policy search, evidence mapping and detail lookup')
    if target in {'llm', 'all'}:
        require('OPENAI_API_KEY')
        result = await LLMReasoner().scope('청년 월세 지원 정책을 알려줘')
        if not result.in_scope:
            raise RuntimeError('LLM returned an unexpected scope decision')
        print('PASS: real LLM structured response')
    if target in {'graph', 'all'}:
        require('OPENAI_API_KEY'); require('YOUTH_POLICY_API_KEY')
        class EmptyRetriever:
            async def search(self, *args):
                return []
        # Intentionally empty RAG tests live external supplementation, not HTTP deployment.
        service = PolicyRagService(EmptyRetriever(), LLMReasoner(), GraphPolicyAgent())
        result = await service.answer_question(RAGRequest(
            question=f'{keyword} 관련 정책과 확인할 조건을 안내해줘',
            profile=UserProfile(age=25, region='서울', income='가구 기준중위소득 100% 이하',
                                statuses=['unemployed'], interests=['housing'], details=['월세·주거비'])))
        if result.api_status != 'used' or result.node_path.count('supplement') != 1:
            raise RuntimeError('Live Graph did not obtain policy API evidence')
        if result.status != 'answered' or not result.citations:
            raise RuntimeError('Live Graph did not produce an evidence-backed answer; inspect data/model quality separately')
        print('PASS: live Graph supplementation, reassessment, comparison and cited answer')


def main():
    target = os.getenv('LIVE_TARGET', 'kure')
    if target not in {'kure', 'policy', 'llm', 'graph', 'all'}:
        raise ValueError('Unsupported integration target')
    if target in {'kure', 'all'}:
        kure()
    if target != 'kure':
        asyncio.run(providers(target))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Provider exceptions can include authenticated URLs; never print the original.
        raise SystemExit('FAIL: live integration. Check secrets, network, provider availability and policy evidence.') from None
