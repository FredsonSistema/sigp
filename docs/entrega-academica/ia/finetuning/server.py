from __future__ import annotations

import os
import threading

import torch
from flask import Flask, jsonify, request
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
MODEL_REVISION = "7ae557604adf67be50417f59c2c2f167def9a775"
ADAPTER_PATH = os.environ.get("SIGP_LORA_ADAPTER_PATH", "/models/adapter")
MODEL_NAME = "Qwen2.5-0.5B-Instruct+SIGp-LoRA"
MAX_INPUT_CHARS = 100_000
CPU_THREADS = int(os.environ.get("MODEL_CPU_THREADS", "6"))

torch.set_num_threads(max(1, CPU_THREADS))
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    revision=MODEL_REVISION,
    dtype=torch.float32,
    low_cpu_mem_usage=True,
)
model = PeftModel.from_pretrained(base_model, ADAPTER_PATH, is_trainable=False)
model.eval()
model.config.use_cache = True
generation_lock = threading.Lock()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "model": MODEL_NAME,
        "base_model": MODEL_ID,
        "base_revision": MODEL_REVISION,
        "adapter": "sigp-lora",
    })


@app.post("/classify")
def classify():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"system", "prompt"}:
        return jsonify({"ok": False, "error": "Envie somente system e prompt."}), 400
    system = payload["system"]
    prompt = payload["prompt"]
    if not isinstance(system, str) or not isinstance(prompt, str):
        return jsonify({"ok": False, "error": "system e prompt devem ser texto."}), 400
    if not system.strip() or not prompt.strip() or len(system) + len(prompt) > MAX_INPUT_CHARS:
        return jsonify({"ok": False, "error": "Prompt vazio ou excede o limite permitido."}), 400

    encoded = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
    )
    input_ids = encoded["input_ids"]
    with generation_lock, torch.inference_mode():
        generated = model.generate(
            input_ids,
            max_new_tokens=160,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    response = tokenizer.decode(generated[0, input_ids.shape[-1]:], skip_special_tokens=True)
    return jsonify({"response": response, "model": MODEL_NAME})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5011, threaded=True)
