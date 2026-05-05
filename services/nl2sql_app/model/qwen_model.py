from __future__ import annotations

import os
from typing import Any

import mlflow.pyfunc
import pandas as pd
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


class QwenModel(mlflow.pyfunc.PythonModel):
    def load_context(self, context: mlflow.pyfunc.PythonModelContext) -> None:
        model_id = context.model_config.get("model_id", "Qwen/Qwen2.5-3B-Instruct")
        max_new_tokens = int(context.model_config.get("max_new_tokens", 256))
        temperature = float(context.model_config.get("temperature", 0.0))
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.device = os.environ.get("NL2SQL_MODEL_DEVICE", "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
            device_map=None,
            trust_remote_code=True,
        )
        self.model.to(self.device)
        self.model.eval()

    def _generate(self, prompt: str) -> str:
        messages = [
            {"role": "system", "content": "Return only SQL query. No markdown."},
            {"role": "user", "content": prompt},
        ]
        rendered = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        tokens = self.tokenizer(rendered, return_tensors="pt").to(self.device)
        with torch.no_grad():
            output = self.model.generate(
                **tokens,
                max_new_tokens=self.max_new_tokens,
                do_sample=self.temperature > 0,
                temperature=max(0.01, self.temperature),
                pad_token_id=self.tokenizer.eos_token_id,
            )
        generated = output[0][tokens.input_ids.shape[-1] :]
        text = self.tokenizer.decode(generated, skip_special_tokens=True)
        return text.strip()

    def predict(self, context: mlflow.pyfunc.PythonModelContext, model_input: Any) -> list[str]:
        if isinstance(model_input, pd.DataFrame):
            prompts = model_input["prompt"].astype(str).tolist()
        elif isinstance(model_input, dict):
            prompts = [str(model_input["prompt"])]
        else:
            prompts = [str(x) for x in model_input]
        return [self._generate(prompt) for prompt in prompts]
