from typing import List, Optional, Dict, Any
import asyncio
from app.config import settings

# OpenAI
from openai import OpenAI

# Gemini
import google.generativeai as genai


class OpenAIService:
    """
    Generic LLM service for chat_module.
    Supports:
    - OpenAI (text + image URLs)
    - Gemini (text + PDF/URL context, image URLs included in prompt)
    """

    def __init__(self):
        self.provider = (settings.chat_provider or "gemini").lower()

        # OpenAI setup
        self.openai_client = None
        if settings.openai_api_key:
            self.openai_client = OpenAI(api_key=settings.openai_api_key)
        self.openai_model = "gpt-4-turbo-preview"
        self.openai_vision_model = "gpt-4-vision-preview"

        # Gemini setup
        self.gemini_model_name = "gemini-1.5-pro"
        self.gemini_model = None
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.gemini_model = genai.GenerativeModel(self.gemini_model_name)

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[str]] = None,  # Deprecated - images should be in messages
        web_context: Optional[str] = None,
        pdf_context: Optional[str] = None,
    ) -> str:
        """
        Generate a response using the configured LLM provider.

        Multimodal-style context:
        - Images: passed as image URLs in messages.
        - PDFs: pre-processed into text and passed via pdf_context.
        """
        if self.provider == "gemini" and self.gemini_model is not None:
            return await self._generate_with_gemini(messages, web_context, pdf_context)
        elif self.openai_client is not None:
            return await self._generate_with_openai(messages, web_context)
        else:
            raise Exception("No valid LLM provider configured (OpenAI or Gemini).")

    async def _generate_with_openai(
        self,
        messages: List[Dict[str, Any]],
        web_context: Optional[str] = None,
    ) -> str:
        """OpenAI implementation (kept for compatibility)."""
        api_messages: List[Dict[str, Any]] = []

        for msg in messages:
            message_content: List[Dict[str, Any]] = []

            # Add text content
            if msg.get("content"):
                message_content.append(
                    {
                        "type": "text",
                        "text": msg["content"],
                    }
                )

            # Add images if present (for current message)
            if msg.get("image_urls"):
                for image_url in msg["image_urls"]:
                    message_content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                            },
                        }
                    )

            api_messages.append(
                {
                    "role": msg["role"],
                    "content": message_content if message_content else msg.get("content", ""),
                }
            )

        # Add web context if available
        if web_context:
            system_message = {
                "role": "system",
                "content": f"Additional context from web search:\n\n{web_context}\n\nUse this information to provide accurate and up-to-date answers.",
            }
            api_messages.insert(0, system_message)

        # Determine which model to use (check if any message has images)
        use_vision = any(
            msg.get("image_urls") and len(msg.get("image_urls", [])) > 0 for msg in messages if isinstance(msg, dict)
        )
        model = self.openai_vision_model if use_vision else self.openai_model

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.openai_client.chat.completions.create(
                    model=model,
                    messages=api_messages,
                    temperature=0.7,
                    max_tokens=2000,
                    timeout=60.0,
                ),
            )

            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    async def _generate_with_gemini(
        self,
        messages: List[Dict[str, Any]],
        web_context: Optional[str] = None,
        pdf_context: Optional[str] = None,
    ) -> str:
        """
        Gemini implementation.

        - Flattens conversation into a single prompt with roles.
        - Appends web_context and pdf_context as additional sections.
        - Image URLs are included as text references (Gemini can sometimes fetch from URLs).
        """
        # Build a textual transcript of the conversation
        convo_lines: List[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            image_urls = msg.get("image_urls") or []
            line = f"{role.upper()}: {content}"
            if image_urls:
                line += "\nIMAGE URLS:\n" + "\n".join(image_urls)
            convo_lines.append(line)

        prompt_parts: List[str] = []

        if web_context:
            prompt_parts.append(
                "WEB CONTEXT (from web search):\n"
                f"{web_context}\n"
                "----\n"
            )

        if pdf_context:
            prompt_parts.append(
                "PDF CONTEXT (extracted text from uploaded PDFs):\n"
                f"{pdf_context}\n"
                "----\n"
            )

        prompt_parts.append("CONVERSATION:\n" + "\n\n".join(convo_lines))
        prompt_parts.append(
            "You are a helpful assistant. Use the WEB CONTEXT and PDF CONTEXT when relevant, "
            "but prioritize the latest and most reliable information. Answer the user's last message."
        )

        full_prompt = "\n\n".join(prompt_parts)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.gemini_model.generate_content(
                    full_prompt,
                    generation_config={
                        "temperature": 0.7,
                        "max_output_tokens": 2000,
                    },
                ),
            )
            # google-generativeai returns .text for plain responses
            return response.text
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

    async def generate_heading(
        self,
        first_message: str,
        conversation_summary: Optional[str] = None,
    ) -> str:
        """
        Generate a chat heading based on the first message or conversation summary.
        Uses the configured provider.
        """
        prompt = (
            "Generate a concise, descriptive heading (max 50 characters) for a chat conversation.\n\n"
            f"First message: {first_message}\n"
        )
        if conversation_summary:
            prompt += f"Conversation summary: {conversation_summary}\n"
        prompt += "\nReturn only the heading, nothing else."

        # Prefer Gemini if configured
        if self.provider == "gemini" and self.gemini_model is not None:
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.gemini_model.generate_content(
                        prompt,
                        generation_config={
                            "temperature": 0.5,
                            "max_output_tokens": 50,
                        },
                    ),
                )
                heading = (response.text or "").strip()
                if len(heading) > 50:
                    heading = heading[:47] + "..."
                return heading
            except Exception as e:
                raise Exception(f"Failed to generate heading with Gemini: {str(e)}")

        # Fallback to OpenAI
        if self.openai_client is None:
            raise Exception("No LLM provider configured for heading generation.")

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.openai_client.chat.completions.create(
                    model=self.openai_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that generates concise chat headings.",
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    temperature=0.5,
                    max_tokens=50,
                    timeout=30.0,
                ),
            )

            heading = response.choices[0].message.content.strip()
            if len(heading) > 50:
                heading = heading[:47] + "..."
            return heading
        except Exception as e:
            raise Exception(f"Failed to generate heading: {str(e)}")

    def should_use_web_scraping(self, message: str) -> bool:
        """
        Determine if web scraping should be used based on the message content.
        """
        keywords = [
            "current",
            "recent",
            "latest",
            "today",
            "now",
            "2024",
            "2025",
            "news",
            "update",
            "happening",
            "what is",
            "who is",
            "when did",
            "search",
            "find",
            "look up",
            "information about",
        ]

        message_lower = message.lower()
        return any(keyword in message_lower for keyword in keywords)
