# DiscordBot
## python 3.11-slim, discord.py 2.5.2, yt-dlp 2025.06.30 기준
디스코드에서 음악 틀어주는 봇들 리소스 너무 많이 써서 작동하지 않을 때 홈서버에 추가해서 개인적으로 쓰세요.
---
### Docker 빌드 후 run 할 때 -e <DISCORD_TOKEN> 입력 필수!!!
---
명령어 세트 commands 폴더에 넣은 뒤 모듈화  
bind mount 옵션 허용 후 commands에 명령어 파일 추가 가능  
\_\_init\_\_.py에서 미리 함수로 묶어 bot.py에서 commands 임포트 후 바로 사용할 수 있도록 처리
---
## 기능 목록 (기능 추가 예정)
### 음악재생
~~join: 음성채널 입장~~  
leave: 음성채널 퇴장  
loop: 반복재생(토글)
pause: 일시정지  
play: 검색어 또는 링크(영상 or 재생목록) 재생, join만 하고 나갈 경우 leave 전까지 나갈 수 없어 play에 join 명령어 통합  
pli: 현재 재생 중인 곡, 다음 곡, 재생목록 길이를 보여줌  
resume: 일시정지 해제  
skip: 건너뛰기  
stop: 재생목록 삭제 및 음악 중지  

_기본적으로 재생목록 기능 포함 및 음악 재생 없을 시 자동퇴장 기능 포함, leave는 강제퇴장_  
