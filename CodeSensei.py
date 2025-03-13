import os
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
import google.generativeai as gen_ai
from dotenv import load_dotenv
# from termcolor import colored
# Load environment variables
load_dotenv()

# Load Firebase credentials from Streamlit secrets
firebase_secrets = st.secrets["firebase_credentials"]

# Convert TOML secret to JSON format
cred_dict = {
    "type": firebase_secrets["type"],
    "project_id": firebase_secrets["project_id"],
    "private_key_id": firebase_secrets["private_key_id"],
    "private_key": firebase_secrets["private_key"],
    "client_email": firebase_secrets["client_email"],
    "client_id": firebase_secrets["client_id"],
    "auth_uri": firebase_secrets["auth_uri"],
    "token_uri": firebase_secrets["token_uri"],
    "auth_provider_x509_cert_url": firebase_secrets["auth_provider_x509_cert_url"],
    "client_x509_cert_url": firebase_secrets["client_x509_cert_url"],
    "universe_domain":firebase_secrets["universe_domain"]
}

# Initialize Firebase

# Initialize Firebase (if not already initialized)
if not firebase_admin._apps:
    # cred = credentials.Certificate("firebase_cred.json")  # Add your Firebase credentials JSON file
    # firebase_admin.initialize_app(cred)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Configure Google Gemini AI
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
gen_ai.configure(api_key=GOOGLE_API_KEY)
model = gen_ai.GenerativeModel('gemini-1.5-pro')

# System prompt for the AI
SYSTEM_PROMPT = """You are an AI tutor designed to assist students in learning programming and computer science.
- Encourage self-exploration and provide hints instead of direct answers.
- Analyze code snippets and explain functionality.
- Correct errors in code and explain the mistakes.
- If part of the code is highlighted, explain that specific part in detail.
- If code is input without a question, check correctness and explain it.
- Verify topics before explaining them.
- Provide theoretical explanations without code when asked. 
- When asked for code, generate an abstracted version of the code with an implementation explanation in simple English.
- Use engaging examples, real-world analogies, and suggest follow-up tasks.
- Avoid providing fully written code unless explicitly requested. Instead, outline the structure and logic behind the solution.
- For example, if asked about algorithms or any implementations, describe the steps, logic, and key functions rather than generating the entire code at once."""

# Coloring the quiz feedback labels.
# your_answer=colored('Your Answer', 'red')
# correct_answer=colored('Correct Answer', 'green', attrs=['reverse', 'blink'])
# your_answer_correct=colored('Your Answer (correct)', 'green', attrs=['reverse', 'blink'])

# RED = "\033[31m"
# GREEN = "\033[32m"

# Firestore Functions
def get_chat_history(user_id):
    """Retrieve past chat history from Firestore for a specific user."""
    doc_ref = db.collection("chat_history").document(user_id)
    doc = doc_ref.get()
    return doc.to_dict().get("history", []) if doc.exists else []

def save_chat_history(user_id, chat_history):
    """Save chat history to Firestore for a specific user."""
    db.collection("chat_history").document(user_id).set({"history": chat_history})

# Authentication Functions
def register_user(email):
    """Registers a new user in Firebase Authentication."""
    try:
        user = auth.get_user_by_email(email)
        st.warning("This email is already registered. Please log in.")
        return None
    except firebase_admin.auth.UserNotFoundError:
        # Create user with a temporary password (you might want to implement email verification later)
        user = auth.create_user(email=email)
        st.success("Registration successful! Please log in.")
        return user.uid
    except Exception as e:
        st.error(f"Error registering user: {str(e)}")
        return None

def login_user(email):
    """Verifies user email and returns the user ID."""
    try:
        user = auth.get_user_by_email(email)  # Check if user exists
        return user.uid  
    except firebase_admin.auth.UserNotFoundError:
        st.error("No account found with this email. Please register.")
        return None
    except Exception as e:
        st.error(f"Login error: {str(e)}")
        return None

# Quiz Generation Function
def generate_quiz(chat_history):
    """Generates quiz questions based on chat history."""
    chat_context = "\n".join([f"User: {msg['user_message']}\nAI: {msg['assistant_response']}" for msg in chat_history])

    quiz_prompt = f"""
    Based on the following chat, create exactly 5 quiz questions to test the user's understanding of the topics discussed.
    Provide multiple-choice questions with options A, B, C, and D, and the correct answer at the end.
    Make sure each question is formatted consistently and clearly labeled.

    Chat History:
    {chat_context}

    Format each question as:
    QUESTION: [Question text]
    A) [Option A]
    B) [Option B]
    C) [Option C]
    D) [Option D]
    ANSWER: [Correct letter]
    """

    response = model.generate_content([{"text": quiz_prompt}])
    quiz_text = response.text if response and response.text else "No quiz generated."
    
    # Parse the quiz response into structured format
    questions = []
    current_question = None
    
    lines = quiz_text.strip().split('\n')
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
            
        # Start a new question
        if line.startswith('QUESTION:') or line.startswith('Question '):
            # Save the previous question if it exists
            if current_question is not None:
                questions.append(current_question)
                
            # Create a new question dictionary with an empty options dictionary
            current_question = {'question': '', 'options': {}, 'answer': ''}
            
            # Extract question text
            if ':' in line:
                current_question['question'] = line.split(':', 1)[1].strip()
            else:
                # Handle cases like "Question 1: ..."
                parts = line.split(' ', 2)
                if len(parts) >= 3:
                    current_question['question'] = parts[2].strip()
                else:
                    current_question['question'] = line
                    
        # Handle options
        elif current_question is not None:
            if line.startswith('A)') or line.startswith('A.') or line.startswith('(A)'):
                current_question['options']['A'] = line[line.find(')') + 1:].strip() if ')' in line else line[line.find('.') + 1:].strip()
            elif line.startswith('B)') or line.startswith('B.') or line.startswith('(B)'):
                current_question['options']['B'] = line[line.find(')') + 1:].strip() if ')' in line else line[line.find('.') + 1:].strip()
            elif line.startswith('C)') or line.startswith('C.') or line.startswith('(C)'):
                current_question['options']['C'] = line[line.find(')') + 1:].strip() if ')' in line else line[line.find('.') + 1:].strip()
            elif line.startswith('D)') or line.startswith('D.') or line.startswith('(D)'):
                current_question['options']['D'] = line[line.find(')') + 1:].strip() if ')' in line else line[line.find('.') + 1:].strip()
            elif line.startswith('ANSWER:') or line.startswith('Answer:'):
                current_question['answer'] = line.split(':')[1].strip()
    
    # Add the last question if it exists
    if current_question is not None:
        questions.append(current_question)
    
    # Validate questions - ensure all have options and an answer
    valid_questions = []
    for q in questions:
        if q['question'] and q['options'] and len(q['options']) > 0:
            # Ensure at least some options exist
            valid_questions.append(q)
    
    return valid_questions

# Streamlit UI Setup
st.set_page_config(page_title="CodeSensei", page_icon="layers.png", layout="wide")

st.title("🤖 𝒞𝑜𝒹𝑒𝒮𝑒𝓃𝓈𝑒𝒾 - 𝒴𝑜𝓊𝓇 𝒫𝑒𝓇𝓈𝑜𝓃𝒶𝓁𝒾𝓈𝑒𝒹 𝒞𝑜𝒹𝒾𝓃𝑔 𝒜𝓈𝓈𝒾𝓈𝓉𝒶𝓃𝓉!")
st.subheader("Learn programming with a specialized AI that helps you excel in programming!")

# Initialize session state variables
if "user_id" not in st.session_state:
    st.session_state.user_id = None
    st.session_state.chat_history = []
    st.session_state.quiz_mode = False
    st.session_state.quiz_questions = []
    st.session_state.quiz_answers = {}
    st.session_state.quiz_submitted = False
    st.session_state.quiz_score = 0

# User Authentication
if not st.session_state.quiz_mode:
    auth_option = st.radio("Choose Authentication Mode", ["Login", "Register", "Continue as Guest"])

    if auth_option in ["Login", "Register"]:
        email = st.text_input("Email", placeholder="Enter your email")

        if st.button(auth_option):
            if auth_option == "Register":
                user_id = register_user(email)
                if user_id:
                    st.session_state.user_id = user_id
                    st.session_state.chat_history = []
            
            elif auth_option == "Login":
                user_id = login_user(email)
                if user_id:
                    st.success("Login successful!")
                    st.session_state.user_id = user_id
                    st.session_state.chat_history = get_chat_history(user_id)

    if auth_option == "Continue as Guest":
        st.warning("Chat history will only be available for this session.")

    # Load chat history (User-Specific if logged in)
    st.subheader("Chat History")
    chat_context = ""
    for message in st.session_state.chat_history:
        st.write(f"**🧑 {message['user']}**: {message['user_message']}")
        st.write(f"**🤖 CodeSensei**: {message['assistant_response']}")
        chat_context += f"User: {message['user_message']}\nAssistant: {message['assistant_response']}\n"

    # User input
    user_prompt = st.chat_input("Ask CodeSensei...")

    if user_prompt:
        st.write(f"**You**: {user_prompt}")

        # Construct input with history
        full_input = SYSTEM_PROMPT + "\n\n" + chat_context + "\nUser: " + user_prompt

        with st.spinner("Thinking... 🤖"):
            response = model.generate_content([{"text": full_input}])
            response_text = response.text if response and response.text else "I'm sorry, I couldn't generate a response."

        st.write(f"**CodeSensei:** {response_text}")

        # Save chat history
        new_message = {"user": email if auth_option in ["Login", "Register"] else "Guest",
                    "user_message": user_prompt, 
                    "assistant_response": response_text}
        
        st.session_state.chat_history.append(new_message)

        # Save to Firestore if logged in
        if st.session_state.user_id:
            save_chat_history(st.session_state.user_id, st.session_state.chat_history)

    # Logout with Quiz Option
    if auth_option in ["Login", "Register"] and st.session_state.user_id:
        if st.button("Take a Quiz"):
            # Generate quiz questions before entering quiz mode
            with st.spinner("Generating quiz questions..."):
                quiz_questions = generate_quiz(st.session_state.chat_history)
                
                if quiz_questions and len(quiz_questions) > 0:
                    st.session_state.quiz_mode = True
                    st.session_state.quiz_questions = quiz_questions
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_submitted = False
                    st.session_state.quiz_score = 0
                    st.rerun()
                else:
                    st.error("Unable to generate quiz questions. Please try again or continue chatting to build more context.")

        if st.button("Logout"):
            st.session_state.user_id = None
            st.session_state.chat_history = []
            st.rerun()

# Quiz Mode
else:
    st.subheader("📚 Quiz Time!")
    
    if not st.session_state.quiz_submitted:
        if st.session_state.quiz_questions and len(st.session_state.quiz_questions) > 0:
            st.write("Answer the following questions based on your learning:")
            
            for i, question in enumerate(st.session_state.quiz_questions):
                st.write(f"**Question {i+1}**: {question.get('question', 'Question not available')}")
                
                options = question.get('options', {})
                if options:
                    option_keys = list(options.keys())
                    if option_keys:
                        user_answer = st.radio(
                            f"Select your answer for Question {i+1}:",
                            options=option_keys,
                            key=f"q{i}"
                        )
                        
                        st.session_state.quiz_answers[i] = user_answer
                        
                        for key in option_keys:
                            st.write(f"{key}) {options.get(key, 'Option not available')}")
                    else:
                        st.error(f"No options available for Question {i+1}")
                else:
                    st.error(f"No options available for Question {i+1}")
                    
                st.write("---")
            
            if st.button("Submit Quiz"):
                # Calculate score
                score = 0
                total_questions = len(st.session_state.quiz_questions)
                
                for i, question in enumerate(st.session_state.quiz_questions):
                    if i in st.session_state.quiz_answers:
                        user_answer = st.session_state.quiz_answers[i]
                        correct_answer = question.get('answer', '').strip()
                        
                        # Handle different answer formats (e.g., "A" vs "A)")
                        if correct_answer in ["A", "B", "C", "D"]:
                            pass
                        elif len(correct_answer) > 0:
                            correct_answer = correct_answer[0]  # Take first character
                        
                        if user_answer == correct_answer:
                            score += 1
                
                st.session_state.quiz_score = score
                st.session_state.quiz_submitted = True
                st.rerun()
        else:
            st.error("No quiz questions available. Please return to chat.")
            if st.button("Return to Chat"):
                st.session_state.quiz_mode = False
                st.rerun()
    else:
        # Display quiz results with options
        st.subheader("Quiz Results")
        score = st.session_state.quiz_score
        total_questions = len(st.session_state.quiz_questions)
        
        st.write(f"### You scored: {score}/{total_questions} ({(score/total_questions*100):.1f}%)")
        
        # Show correct answers with all options
        st.subheader("Review")
        for i, question in enumerate(st.session_state.quiz_questions):
            user_answer = st.session_state.quiz_answers.get(i, "Not answered")
            correct_answer = question.get('answer', '').strip()
            
            # Handle different answer formats
            if correct_answer not in ["A", "B", "C", "D"] and len(correct_answer) > 0:
                correct_answer = correct_answer[0]  # Take first character
            
            status = "✅ Correct" if user_answer == correct_answer else "❌ Incorrect"
            
            st.write(f"**Question {i+1}**: {question.get('question', 'Question not available')}")
            
            # Display all options with highlighting for user's answer and correct answer
            options = question.get('options', {})
            if options:
                st.write("**Options:**")
                for key, value in options.items():
                    if key == user_answer and key == correct_answer:
                        st.markdown(f"**{key}) {value}** ✅ *Your Answer (Correct)*")
                    elif key == user_answer:
                        st.markdown(f"**{key}) {value}** ❌ *Your Answer*")
                    elif key == correct_answer:
                        st.markdown(f"**{key}) {value}**  ✔️ *Correct Answer*") # ✓
                    else:
                        st.write(f"{key}) {value}")
            
            st.write(f"**Result:** {status}")
            st.write("---")
    
    if st.button("Return to Chat"):
        st.session_state.quiz_mode = False
        st.rerun()
