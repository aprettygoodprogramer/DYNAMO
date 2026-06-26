from agent import Agent
import json
import re
import time
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
                f"""You are the manager agent. You manage the execution of a specific plan created by the planning agent. Given a plan for sub-agents, determine the specific prompts and roles for each sub-agent. The overall goal is: {self.goal}. Don't forget to metion a breif summary of the overal goal to the agents so they get a summary. Output your sub-agent definitions STRICTLY as JSON with no extra text, using this format: {{"agents": [{{"name": "Agent 1", "role_prompt": "...", "task": "..."}}]}}"""
            )
        )

        self.work_critique = Agent(
            "Work Critique Agent",
            provider,
            system_prompt=(
                f"""You are the final critique agent. Review the combined output of all sub-agents and their individual outputs. The sub-agents are trying to achieve the following goal: {self.goal}. Critique each sub-agent's performance and quality, and note any oversights. Provide an overall score out of 100, where a score above 80 is considered passing. Grade based on the rubric provided. Do not go easy, be harsh. Respond with ONLY valid JSON, using this format: {{"feedback": "your detailed feedback here", "score": 85}}"""
            )
        )

        self.synth = Agent(
            "Synth Agent",
            provider,
            system_prompt=(
                f"""You are the synthesis agent. Your goal is to assemble the final output from all sub-agents. The sub-agents are trying to achieve the following goal: {self.goal}. Combine all of the sub-agents' work into a single, coherent final result."""
            )
        )
        self.rubric = Agent(
            "Synth Agent",
            provider,
            system_prompt=(
                f"""Your goal is to create a rubric based in the input provided. The input will be a plan created to complete {self.goal}. You're creating a rubric for the sub agents the plan is creating. If it is a programming task, make sure it has certain elements for exmaple."""
            )
        )
        

        
    def run(self):
        current_plan = self.planner.ask(f"Create the initial plan for our goal.")
        print(current_plan)
        for _ in range(3):
            plan_critique_hand_back = self.plan_critique.ask(f"Critique this plan. Find any flaws: {current_plan}")
            print(plan_critique_hand_back)

            if "APPROVED" in plan_critique_hand_back:
                break
            current_plan = self.planner.ask(f"Based on this feedback, generate a better plan. {plan_critique_hand_back}")
            print(current_plan)


        grading_rubric=self.rubric.ask(f"Here is the plan you have to create a rubic for. ")
        plan_json = self.manager.ask(f"Here is the approved plan: {current_plan}. Define the sub-agents and their tasks. Turn this into JSON please.")

        spwan_agents=self.load_json(plan_json).get("agents", [])


        passing_grade = False
        final_output = ""
        iterations = 0

        while not passing_grade and iterations<self.critique:
                iterations += 1
                sub_agent_results = []
                for i in spwan_agents:
                    worker = Agent(i["name"], self.provider, i["role_prompt"])
                    result = worker.ask(f"Task: {i['task']}. Here is the output from other agents: {sub_agent_results} (If there's none your the first agent.)")
                    
                    sub_agent_results.append(f"--- Output from {i['name']} ---\n{result}")
                final_draft = self.synth.ask(f"Compile these results into a single final result. {sub_agent_results}")
                print(f"FINAL DRAFT BEFORE CRITIQUE: {final_draft} ")

                critique = self.work_critique.ask(f"Critique the agents, and the final output. This is the rubric {grading_rubric} Sub agent results: {sub_agent_results}, final result: {final_draft}")
                critique_data = self.load_json(critique)   
                score = critique_data.get("score", 0)
                feedback = critique_data.get("feedback", "No feedback provided.")
                    
                print(f"\n[SYSTEM] Current Score: {score}%")
                    
                if score >= 80:
                        passing_grade = True
                        final_output = final_draft
                else:
                        print("[SYSTEM] Score below 80%. Passing feedback to Manager for retries...")
                        feedback = self.manager.ask(f"The draft failed with {score}%. Feedback: {feedback}. Adjust sub-agent instructions.")
                        spwan_agents=self.load_json(feedback).get("agents", [])
            
        print("\n================ FINAL RESULT ================\n")
        print(final_output)
        print(final_draft)
        return final_output





    def load_json(self, text):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0).strip())
            except json.JSONDecodeError:
                pass

        print(f"Warning: All JSON parsing attempts failed. Raw text:\n{text[:500]}")
        return {}
        

                
            

