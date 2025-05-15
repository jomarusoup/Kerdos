- Name: kerdos - ATAS(Auto Trading AI System)
	- kerdos: 그리스어로 이익

## 🏆 Goal

LMM Large Multimodel Models
- GPT-4o 이상 모델에서 차트의 이미지를 분석가능
- AI에게 보여줄 수 있는 데이터의 양 : Context

인간이 투자 판단을 내리는 과정을 자동화시켜 AI가 인간처럼 데이터를 보고, 듣고 종합적인 추론 및 판단 가능한 프로그램 개발

- 데이터 + 보조지표 / 차트 모양 / 뉴스 / 커뮤니티 / 투자 철학 > 인간 vs AI > 매수/매도

## 📂 Description
- 전략 + 데이터  > 투자판단(Chatgpt) > 업비트(매수/매도/홀드 + 이유) > 매매 기록(DB) + Streamlit 실시간 현황 사이트 > 회고 및 재귀 개선으로 전략 + 데이터 수정 > 반복
- AI에게 제공할 데이터
	- 거래소 데이터
	- 차트 데이터 (OHLCV + 보조지표)
	- 차트 이미지
	- 공포 탐욕 인덱스
	- 최신 뉴스 테이터
	- 유튜브 데이터
	- 이전 매매 데이터(회고용)
	- 추가 기능
		- 엔벨로프 /

![[Screenshot 2025-01-25 at 13.35.10.png]]

### 서버

- OS: Rocky Linux 8.10 (Green Obsidian)
- KERNEL: 4.18.0-553.el8_10.x86_64
- CPU: Intel(R) Core(TM) i5-8400 @ 2.80GHz
	- 6 Cores / 6 Threads
- MEMORY: 8GB DDR4
	- 4GB x 2 (Dual-Channel Configuration)
- STORAGE : SSD

>
- SERVER: Dev1
	- home: kerdos
	- IP:PORT
		- Private

### 서버 설정

- Server Intial Setting
	- Linux Initial Settings
	- .bash_profile
	- .vimrc

- 개발 언어 및 프레임워크:
	- [ ] 서버 Lang: python 3.12.2
	- [ ] pyrhon lib
		- [ ] python-dotenv
		- [ ] openai
		- [ ] pyupbit
    - [ ] ta
	- [ ] 데이터베이스:
    - [ ] SQL Lite
    - [ ] Postgresql
	- [ ] 버전 관리 시스템 (VCS): GitHub
- 차후 추가
	- [ ] 결과를 확인 가능한 클라이언트 혹은 사이 개발
	- [ ] Docker
	- [ ] Github Action
	- [ ] Kubernetes
	- [ ] AWS
