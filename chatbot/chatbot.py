from redbot.core import commands
import dialogflow_v2 as dialogflow
import uuid
import asyncio


class ChatBot(commands.Cog):
    """Dialogflow-powered chatbot"""

    def __init__(self, bot):
        self.bot = bot
        self.project_id = "duckychat"
        self.language_code = "en"
        self.session_client = dialogflow.SessionsClient()

    async def detect_intent(self, text, session_id):
        session = self.session_client.session_path(self.project_id, session_id)

        text_input = dialogflow.TextInput(text=text, language_code=self.language_code)
        query_input = dialogflow.QueryInput(text=text_input)

        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.session_client.detect_intent(
                session=session, query_input=query_input
            ),
        )

        return response.query_result.fulfillment_text

    @commands.command()
    async def chat(self, ctx, *, message: str):
        """Talk to the Dialogflow bot"""
        session_id = f"{ctx.author.id}-{uuid.uuid4()}"
        reply = await self.detect_intent(message, session_id)

        if not reply:
            reply = "🤖 ...I don't know how to respond to that yet."

        await ctx.send(reply)


def setup(bot):
    bot.add_cog(ChatBot(bot))
