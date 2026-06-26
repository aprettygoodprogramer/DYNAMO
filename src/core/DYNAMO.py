from agent import Agent

class DYNAMO:
    def __init__(self, provider, critique, goal):
        self.provider = provider
        self.critique = critique
        self.goal=goal
        self.planner = Agent(
            "Planning Agent", 
            provider, 
            system_prompt=(
                f"""You are the planning agent. Your goal is to take the following goal: {self.goal}, and create a plan for sub-agents. Outline what agents need to be created for the task to be completed. Break down the task into multiple smaller tasks that can be performed by individual agents. For a programming example, you could have an agent that writes a specific part of the code, and another agent that critiques it. All you need to do is describe each agent and their role."""
            )
        )

        self.plan_critique = Agent(
            "Plan Critique Agent",
            provider,
            system_prompt=(
                f"""You critique the plans of the planning agent. The planning agent is creating a plan for sub-agents in order to complete the following goal: {self.goal}. Review the plan and provide constructive feedback. If the plan is sufficient, end your review with the exact phrase "APPROVED"."""
            )
        )

        self.manager = Agent(
            "Manager Agent",
            provider,
            system_prompt=(
                f"""You are the manager agent. You manage the execution of a specific plan created by the planning agent. Given a plan for sub-agents, determine the specific prompts and roles for each sub-agent. The overall goal is: {self.goal}. Output your sub-agent definitions STRICTLY as JSON with no extra text, using this format: {{"agents": [{{"name": "Agent 1", "role_prompt": "...", "task": "..."}}]}}"""
            )
        )

        self.work_critique = Agent(
            "Work Critique Agent",
            provider,
            system_prompt=(
                f"""You are the final critique agent. Review the combined output of all sub-agents and their individual outputs. The sub-agents are trying to achieve the following goal: {self.goal}. Critique each sub-agent's performance and quality, and note any oversights. Provide an overall score out of 100, where a score above 80 is considered passing. Respond with ONLY valid JSON, using this format: {{"feedback": "your detailed feedback here", "score": 85}}"""
            )
        )

        self.synth = Agent(
            "Synth Agent",
            provider,
            system_prompt=(
                f"""You are the synthesis agent. Your goal is to assemble the final output from all sub-agents. The sub-agents are trying to achieve the following goal: {self.goal}. Combine all of the sub-agents' work into a single, coherent final result."""
            )
        )
        

        
    def run(self):

        None
    

