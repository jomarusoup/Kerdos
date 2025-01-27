#!/bin/bash

# Git 상태 확인
echo "🔍 수정된 파일 및 새로 생성된 파일을 확인 중입니다..."
MODIFIED_FILES=$(git status --short | grep -E "^( M|A| D|\?\?)" | awk '{if ($1 == "??") print $2; else print $2}')

if [ -z "$MODIFIED_FILES" ]; then
    echo "⚠️ 수정되거나 새로 추가된 파일이 없습니다."
    exit 0
fi

# 수정된 파일 리스트 출력
echo "📝 수정되거나 새로 추가된 파일 리스트:"
echo "$MODIFIED_FILES"
echo

# 각 파일마다 커밋 메시지 입력
for FILE in $MODIFIED_FILES; do
    echo "✏️  [$FILE] 파일에 대한 커밋 메시지를 입력하세요:"
    read -r COMMIT_MSG

    # 변경 사항 스테이징
    git add "$FILE"

    # 개별 커밋
    git commit -m "$COMMIT_MSG"

    echo "✅ [$FILE] 커밋 완료: $COMMIT_MSG"
done

# 원격 저장소로 푸쉬
echo "🚀 모든 커밋을 푸쉬 중입니다..."
git push origin main

echo "✅ 모든 작업이 완료되었습니다!"
