"""
Voice Agent Module - STT → LLM → TTS Pipeline
Inspired by LiveKit's approach for real-time voice interactions
"""

import asyncio
import base64
import io
import logging
import os
from typing import AsyncGenerator, Optional, Dict, List
from openai import AsyncOpenAI
from pydantic import BaseModel
import json

logger = logging.getLogger(__name__)


class VoiceConfig(BaseModel):
    """Configuration for voice agent"""
    stt_model: str = "whisper-1"
    llm_model: str = "gpt-4.1-2025-04-14"
    tts_model: str = "tts-1"
    tts_voice: str = "nova"  # alloy, echo, fable, onyx, nova, shimmer
    max_history: int = 10
    temperature: float = 0.7
    system_prompt: str = """You are an intelligent and friendly voice assistant.
You are an agentic AI character with personality and emotions.
Keep your responses natural, conversational, and concise for voice interaction.
Be engaging, helpful, and show personality in your responses."""


class ConversationMessage(BaseModel):
    """Message in conversation history"""
    role: str
    content: str
    timestamp: Optional[float] = None


class VoiceAgent:
    """
    Voice Agent that processes:
    1. Speech-to-Text (STT) using OpenAI Whisper
    2. Language Model (LLM) using GPT-4
    3. Text-to-Speech (TTS) using OpenAI TTS

    Inspired by LiveKit's real-time voice agent architecture
    """

    def __init__(self, api_key: str, config: Optional[VoiceConfig] = None):
        self.client = AsyncOpenAI(api_key=api_key)
        self.config = config or VoiceConfig()
        self.conversation_history: List[ConversationMessage] = []
        self.is_processing = False

        # Initialize with system prompt
        self.conversation_history.append(
            ConversationMessage(
                role="system",
                content=self.config.system_prompt
            )
        )

        logger.info("Voice Agent initialized with config: %s", self.config.model_dump())

    async def transcribe_audio(self, audio_data: bytes, format: str = "webm") -> Optional[str]:
        """
        Speech-to-Text: Convert audio to text using OpenAI Whisper

        Args:
            audio_data: Raw audio bytes
            format: Audio format (webm, mp3, wav, etc.)

        Returns:
            Transcribed text or None if error
        """
        try:
            logger.info(f"Starting transcription, audio size: {len(audio_data)} bytes")

            # Create a file-like object from bytes
            audio_file = io.BytesIO(audio_data)
            audio_file.name = f"audio.{format}"

            # Call Whisper API
            response = await self.client.audio.transcriptions.create(
                model=self.config.stt_model,
                file=audio_file,
                response_format="text"
            )

            transcribed_text = response if isinstance(response, str) else response.text
            logger.info(f"Transcription successful: '{transcribed_text}'")

            return transcribed_text

        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            return None

    async def get_llm_response(self, user_message: str) -> str:
        """
        Language Model: Get intelligent response from GPT-4

        Args:
            user_message: User's transcribed text

        Returns:
            LLM response text
        """
        try:
            # Add user message to history
            self.conversation_history.append(
                ConversationMessage(role="user", content=user_message)
            )

            # Maintain conversation history limit
            if len(self.conversation_history) > self.config.max_history + 1:  # +1 for system message
                # Keep system message and last N messages
                self.conversation_history = [
                    self.conversation_history[0]  # System message
                ] + self.conversation_history[-(self.config.max_history):]

            # Prepare messages for API
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in self.conversation_history
            ]

            logger.info(f"Sending {len(messages)} messages to LLM")
            logger.debug(f"User message: '{user_message}'")

            # Call GPT-4 API
            response = await self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=300  # Keep responses concise for voice
            )

            assistant_message = response.choices[0].message.content

            # Add assistant response to history
            self.conversation_history.append(
                ConversationMessage(role="assistant", content=assistant_message)
            )

            logger.info(f"LLM response: '{assistant_message}'")

            return assistant_message

        except Exception as e:
            logger.error(f"LLM error: {e}", exc_info=True)
            return "I apologize, but I encountered an error processing your request."

    async def synthesize_speech(self, text: str) -> Optional[bytes]:
        """
        Text-to-Speech: Convert text to speech using OpenAI TTS

        Args:
            text: Text to convert to speech

        Returns:
            Audio bytes (MP3 format) or None if error
        """
        try:
            logger.info(f"Synthesizing speech for text: '{text[:50]}...'")

            # Call TTS API
            response = await self.client.audio.speech.create(
                model=self.config.tts_model,
                voice=self.config.tts_voice,
                input=text,
                response_format="mp3"
            )

            # Get audio bytes
            audio_bytes = response.content

            logger.info(f"Speech synthesis successful, audio size: {len(audio_bytes)} bytes")

            return audio_bytes

        except Exception as e:
            logger.error(f"TTS error: {e}", exc_info=True)
            return None

    async def process_voice_input(self, audio_data: bytes, format: str = "webm") -> Dict:
        """
        Complete pipeline: STT → LLM → TTS

        Args:
            audio_data: Raw audio bytes from user
            format: Audio format

        Returns:
            Dictionary with transcription, response text, and audio
        """
        if self.is_processing:
            logger.warning("Already processing a request, skipping...")
            return {
                "error": "Already processing a request",
                "status": "busy"
            }

        self.is_processing = True

        try:
            result = {
                "status": "success",
                "transcription": None,
                "response_text": None,
                "response_audio": None,
                "error": None
            }

            # Step 1: Speech-to-Text
            logger.info("Step 1: Transcribing audio...")
            transcription = await self.transcribe_audio(audio_data, format)

            if not transcription or transcription.strip() == "":
                result["status"] = "error"
                result["error"] = "Could not transcribe audio"
                return result

            result["transcription"] = transcription

            # Step 2: Get LLM Response
            logger.info("Step 2: Getting LLM response...")
            response_text = await self.get_llm_response(transcription)
            result["response_text"] = response_text

            # Step 3: Text-to-Speech
            logger.info("Step 3: Synthesizing speech...")
            response_audio = await self.synthesize_speech(response_text)

            if response_audio:
                # Convert to base64 for transmission
                result["response_audio"] = base64.b64encode(response_audio).decode('utf-8')
            else:
                result["error"] = "Failed to synthesize speech"
                result["status"] = "partial"

            logger.info("Voice pipeline completed successfully")

            return result

        except Exception as e:
            logger.error(f"Voice pipeline error: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

        finally:
            self.is_processing = False

    async def stream_llm_response(self, user_message: str) -> AsyncGenerator[str, None]:
        """
        Stream LLM response word by word for more natural interaction

        Args:
            user_message: User's message

        Yields:
            Chunks of response text
        """
        try:
            # Add user message to history
            self.conversation_history.append(
                ConversationMessage(role="user", content=user_message)
            )

            # Prepare messages
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in self.conversation_history
            ]

            # Stream response
            full_response = ""
            stream = await self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=300,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield content

            # Add to history after completion
            self.conversation_history.append(
                ConversationMessage(role="assistant", content=full_response)
            )

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f"Error: {str(e)}"

    def clear_history(self, keep_system_prompt: bool = True):
        """Clear conversation history"""
        if keep_system_prompt and len(self.conversation_history) > 0:
            self.conversation_history = [self.conversation_history[0]]
        else:
            self.conversation_history = []

        logger.info("Conversation history cleared")

    def get_conversation_summary(self) -> List[Dict]:
        """Get conversation history as list of dicts"""
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp
            }
            for msg in self.conversation_history
            if msg.role != "system"  # Exclude system message
        ]


# Global voice agent instance (will be initialized in main.py)
voice_agent: Optional[VoiceAgent] = None


def get_voice_agent() -> VoiceAgent:
    """Get the global voice agent instance"""
    global voice_agent
    if voice_agent is None:
        raise RuntimeError("Voice agent not initialized. Call initialize_voice_agent() first.")
    return voice_agent


def initialize_voice_agent(api_key: str, config: Optional[VoiceConfig] = None) -> VoiceAgent:
    """Initialize the global voice agent instance"""
    global voice_agent
    voice_agent = VoiceAgent(api_key, config)
    return voice_agent
