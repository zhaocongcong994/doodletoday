"""Isolated OCR process: stdout emits only structured recognition results.
Model downloads/inference happen locally; raw output is never logged by the API.
"""
import contextlib
import json
import sys

if __name__ == '__main__':
    with contextlib.redirect_stdout(sys.stderr):
        from paddleocr import PaddleOCR
        engine=PaddleOCR(use_doc_orientation_classify=True, use_doc_unwarping=False, use_textline_orientation=True, lang='ch')
        results=list(engine.predict(sys.argv[1]))
        blocks=[]
        for result in results:
            obj=result.json
            if isinstance(obj,str): obj=json.loads(obj)
            obj=obj.get('res',obj)
            blocks.extend({'text':str(t), 'confidence':float(s)} for t,s in zip(obj.get('rec_texts',[]),obj.get('rec_scores',[])))
    print(json.dumps(blocks,ensure_ascii=False))
