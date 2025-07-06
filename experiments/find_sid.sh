ENCODED=$(pwd | sed 's#/#-#g')

SID=$(ls -1t ~/.claude/projects/$ENCODED/*.jsonl | head -n1 \
      | sed -E 's#.*/([^/]+)\.jsonl#\1#')

echo "$SID"
